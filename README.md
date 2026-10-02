# kof-publisher

Editorial pipeline + recurring publisher for a company's LinkedIn voice,
written 100% in Kof on top of the real Kof4j surface: KofMD (identity),
KofTime (recurrence with explicit IANA timezone), KofLM (Ollama/OpenAI-style
chat), `kof.orm` over SQLite (state + idempotency ledger) and `kof.process`
(daemon). No stubs: when KofLM is offline the CLI fails with its real cause.

Measured environment: kof 0.5.0-beta, OpenJDK 25 LTS (Temurin). Compiler gaps
found while building this (with repros): [docs/gaps-and-reports.md](docs/gaps-and-reports.md).

## Layout

```
src/            root package (see the ORM entity gap below)
  Main.kf         entry point
  Context.kf      company.kofmd loader (KofMD)
  Recurrence.kf   timezone-safe weekly/interval calendar
  KofLm.kf        KofLM face over kof.http + kof.json (Ollama /api/chat)
  Editorial.kf    generate / validate / revise / dedup
  Store.kf        entities (Publication, Schedule, Occurrence) + kof.orm
  Scheduler.kf    agenda, next occurrence, claim/idempotency, retry
  Targets.kf      PublicationTarget: dryrun + LinkedIn (ugcPosts)
  Publisher.kf    CLI dispatch
  kofmd/          vendored KofMD parser + schemas (schema-gated sections)
tests/
  Cli.kf          end-to-end: spawns the REAL built binary
```

## Commands

```
kof build src --target jvm

java -cp build/classes:$HOME/.local/share/kof/lib/kof.jar:$HOME/.kof/deps/org/xerial/sqlite-jdbc/3.53.4.0/sqlite-jdbc-3.53.4.0.jar Default.Main <cmd>

  init         create company.kofmd template (+ state dir)
  check        validate identity + timezone + KofLM availability
  generate     drafts via KofLM (--topic, --ideas N, --publish-ok)
  list         queue (--status review|approved|...)
  review       show draft + deterministic validation
  approve|reject|cancel <id>
  publish      publish an approved/scheduled publication
  schedule     register an agenda (--name --days mon,wed --at 09:00 [--every N --anchor D])
  schedules    persisted agendas + next occurrence
  sync         load the `# schedule <name>` blocks from company.kofmd
  daemon       run the agenda (STOP file: <store>.stop)
  history      occurrence ledger (never runs an occurrence twice)
```

Global flags: `--company <file>` (default `company.kofmd`), `--store <db>`.

Config (env `KOF_<KEY>` beats `kof.config`): `lm.url` (default
`http://localhost:11434`), `lm.model` (default `qwen3.5:0.8b` — models with a
Ollama thinking models need `"think":false` or a big
`lm.tokens` — `lm.think=true` re-enables thinking), `lm.tokens`,
`lm.timeout`, `publisher.home`, `publisher.store`, `publisher.dryrun.dir`,
`linkedin.api`. LinkedIn credentials come ONLY from secrets
(`KOF_LINKEDIN_ACCESS_TOKEN`, `KOF_LINKEDIN_AUTHOR_URN`) — never from the
company file, never logged (errors pass through `secrets.redact`).

## Tests (24/24 green on the installed kof 0.5.0-beta and the dev jar)

```
kof build src --target jvm
kof test src/Recurrence.kf --target jvm    # 6 calendar/timezone tests
kof test src/Model.kf --target jvm         # status machine + keys
kof test tests --target jvm --timeout 400  # 8 CLI e2e + 3 LM/daemon e2e
```

`tests/FakeLm.kf` runs the FULL pipeline (generate -> review -> approve ->
publish -> history -> dry-run file) against `tests/fake_lm_server.py`, a
fixture that serves the real Ollama chat protocol over a socket — only the
model is deterministic; kof.http, json, ORM and the targets are all live.
Set `KOF_LM_LIVE=<model>` to additionally drive the flow through the local
Ollama (qwen3.5:0.8b measured ~1.5 s/token on CPU — budget `lm.timeout`
accordingly).

`tests/FakeLm.kf` also drives the DAEMON: a weekly agenda due ~90s ahead
must fire autonomously (autonomous+dryrun), a `STOP` file must end it
cleanly, and a restarted daemon must not publish the same occurrence twice
(ledger `loop@<iso>` claim). `recoverAgenda` keeps a stored next occurrence
that is in the future or overdue by <=10 min — a restart catches up, it
never skips a due slot.

`tests/Cli.kf` assumes the KofLM is OFFLINE for the outage test by injecting
`KOF_LM_URL=http://127.0.0.1:1`; it asserts the error is reported as data
(exit code + message), with no stacktrace. Override paths with
`KOF_PUBLISHER_DIR` / `KOF_PUBLISHER_CLASSES` / `KOF_SQLITE_JAR`.

## KOF Lab daily mode (examples/kof-lab.kofmd)

Publishes, every day at 09:30 America/Sao_Paulo, what actually landed in
`lab` in the Kof4j repository — in the author's real voice (Mel Santos:
continuous prose, few dense paragraphs, zero em-dashes, zero coach
cliches, technically precise, humor from real experience). The company
file carries the full 24-rule style guide as a `guide:` list; `src/LabNews.kf`
gathers the day's facts with real git (commits `feat/fix/docs` in the
window, §NNN bugs opened in the ledger, the newest DECISIONS.md vote, the
DOING.md claimed units).

- **Facts, not vibes:** the generation prompt is the digest; a window with
  no news ends with "sem novidades" and publishes NOTHING (the marker file
  under `publisher.home` only advances after a successful publish, so a
  skipped day widens tomorrow's window instead of faking content).
- **Style is enforced, not suggested:** the validator hard-rejects em-dashes,
  generic CTAs, coach sentences, artificial openings and colon/paragraph
  abuse whenever a guide is configured (tested end to end in
  `tests/KofLab.kf`).
- **Once per ~60 days:** `python3 tools/linked_oauth.py` — add
  `http://localhost:8737/callback` as the Redirect URL in the LinkedIn app
  first; open the printed link in Firefox, authorize; the script exchanges
  the code, resolves the person URN via OIDC and writes
  `~/.local/share/kof/linkedin-secrets.env` (chmod 600). Tokens are never
  printed and never touch the repo.
- **Daily:** `tools/koflab-daily.sh` (fetch origin/lab, generate, validate,
  publish to the Posts API). Crontab:
  `30 9 * * * /home/mel/Documentos/kof-publisher/tools/koflab-daily.sh >> /home/mel/Documentos/kof-publisher/var/koflab-daily.log 2>&1`

## Idempotency model

One occurrence = `(schedule name, scheduled-at instant)`, keyed
deterministically (`occurrenceKeyOf`). The daemon CLAIMS the key in the
`Occurrence` ledger BEFORE generating, so a restart, a second daemon, a
retry or a race can never publish the same occurrence twice. A failed
publish keeps the same publication id and retries it (never regenerates a
different post).

## Cross-target status (measured 01/10)

| Target | `kof build src` | Notes |
|--------|-----------------|-------|
| JVM | ✅ builds, 20/20 tests pass | the supported target (SQLite driver on the classpath) |
| JS | ✅ compiles clean (`Default.mjs`) | publisher faces (db/http/process) are JVM-validated only |
| native x86-64 | ❌ compile-time refusal, honest code | `JSN002: LmChatResp has field of type LmMsg not supported by the Native JSON encoder` (nested record in `json.decode<T>`) — flattening the chat response (model/done/content as scalars) unblocks it if a native build is ever needed |
