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

java -cp build/classes:$HOME/.local/share/kof/lib/kof.jar:sqlite-jdbc.jar Default.Main <cmd>

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

## Tests

```
java -jar kof-cli-0.5.0-beta.jar build src --target jvm
java -jar kof-cli-0.5.0-beta.jar test src/Recurrence.kf --target jvm   # 6 calendar/timezone tests
java -jar kof-cli-0.5.0-beta.jar test src/Model.kf --target jvm        # status machine + keys
java -jar kof-cli-0.5.0-beta.jar test tests --target jvm --timeout 300  # 8 CLI + 2 LM e2e
```

`tests/FakeLm.kf` runs the FULL pipeline (generate -> review -> approve ->
publish -> history -> dry-run file) against `tests/fake_lm_server.py`, a
fixture that serves the real Ollama chat protocol over a socket — only the
model is deterministic; kof.http, json, ORM and the targets are all live.
Set `KOF_LM_LIVE=<model>` to additionally drive the flow through the local
Ollama (qwen3.5:0.8b measured ~1.5 s/token on CPU — budget `lm.timeout`
accordingly).

`tests/Cli.kf` assumes the KofLM is OFFLINE for the outage test by injecting
`KOF_LM_URL=http://127.0.0.1:1`; it asserts the error is reported as data
(exit code + message), with no stacktrace. Override paths with
`KOF_PUBLISHER_DIR` / `KOF_PUBLISHER_CLASSES` / `KOF_SQLITE_JAR`.

## Idempotency model

One occurrence = `(schedule name, scheduled-at instant)`, keyed
deterministically (`occurrenceKeyOf`). The daemon CLAIMS the key in the
`Occurrence` ledger BEFORE generating, so a restart, a second daemon, a
retry or a race can never publish the same occurrence twice. A failed
publish keeps the same publication id and retries it (never regenerates a
different post).
