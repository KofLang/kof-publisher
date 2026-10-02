# Gaps & bug reports measured while building kof-publisher

Environment: kof 0.5.0-beta (installed `kof`) and `kof-cli-0.5.0-beta.jar`
built from the current tree — both tested on OpenJDK 25 (Temurin), Linux.
"installed" and "dev-jar" below refer to those two binaries. Repros in
`docs/repros/`.

## BUG-6 — ORM entity in a named package: class descriptor without package (OPEN, both binaries)

> Upstream: **landed on `lab`** as **§566** in
> `Kof4j/docs/bugs-and-gaps/known-bugs.md` (BUG-7 → §565, BUG-8 → §564) —
> commit `f041c66b4` (02/10). Earlier attempts were blocked by the repo-wide
> pre-receive gate (`analyzed <none>` — KofLang/Kof4j **issue #726**); the
> gate degraded to INCONCLUSIVO and the push went through. Numbers moved
> §554-556 → §562-564 → §563-565 → §564-566 as upstream consumed ranges.

`entity` declared in `package app`: compiler emits `Class.forName("Erec")`
(simple name) in `kof_orm_*`, while the class file is `app/Erec.class`.
Any `orm.find/all/where/...` on it dies at runtime:

```
Exception in thread "main" java.lang.NoClassDefFoundError: Erec
```

Measured 01/10 with `kof-cli-0.5.0-beta.jar` — repro:
`docs/repros/orm-entity-package/` (build + run).

Consequences for this project (the reason `src/` is a flat ROOT package):
- entities must live in the root package (`src/Store.kf`);
- root-package symbols are not importable (`import X` resolves to a
  DIRECTORY, not a sibling file — `CompilerImports` treats a dot-less import
  as a package dir), so a separate test root cannot `import` them;
- therefore state persistence is covered by REAL-CLI tests (`tests/Cli.kf`
  spawns the built `Default.Main`), and only self-contained modules
  (`Recurrence.kf`, `Model.kf`) carry unit `test` blocks in-source.
- `kof test src` (dir mode) would run every app file as a test suite and the
  root `Main` is not a `javafx.application.Application` — the launcher error
  is masked by the JavaFX message; another reason tests are split file/dir
  explicitly.

## BUG-4 — installed parser: top-level nested-generic return type (FIXED in dev-jar)

`List<List<String>>` / `Map<String, List<String>>` as a TOP-LEVEL function
return type:

```
error: Expected '>' after type parameters [PARSE075]
```

installed `kof build docs/repros/generic-return.kf` → PARSE075; the same
command with `kof-cli-0.5.0-beta.jar` compiles and runs clean. The identical
shape as a CLASS METHOD parses on both. This blocks nothing here anymore
(dev-jar), but the shipped 0.5.0-beta parser rejects it — worth a release
note. (`Context.kf` still avoids the nested shape with an
`CompanySections(Section, Section)` carrier, so the installed CLI can build
this project too.)

## BUG-5 — nullable primitive return: NOT reproducible (corrected 01/10)

Earlier in the session `Int?` top-level returns were believed to crash the
JVM (VerifyError). Re-measured 01/10 on BOTH binaries with
`docs/repros/nullable-primitive.kf`-style programs:

```
Int? maybe(Int x) { if (x > 0) { return x } return null }
```

compiles AND runs (`none`/value) on installed and dev-jar. The publisher
keeps its `-1`/sentinel style (`parseClock`) only as a convention, not as a
compiler workaround. If the VerifyError recurs, capture the exact lowering.

## BUG-3 — `kof.http` does not wrap JDK failures (OPEN, worked around)

`http.post/get/status` let `java.net.http.*` exceptions (e.g.
`HttpTimeoutException: request timed out`) escape. Kof `catch (String e)` on
an HTTP verb does NOT catch them. Workaround used everywhere here
(`KofLm.kf` `httpPostSafe`, `Targets.kf`): `spawn http.post(...)` +
poll + `try { raw = poll(h) } catch (String e)`, with the real cause surfaced
(`secrets.redact`ed for tokens). `tests/Cli.kf` asserts the outage path
reports DATA and never prints a stacktrace.

## BUG-8 — ORM read lowercases column labels; camelCase entity fields bind NULL (OPEN, both binaries)

`kof_db_query_n` builds the row map with `md.getColumnLabel(i).toLowerCase()`
(`JvmConfigRuntime`), while `orm.create`/`orm.save` write the entity's
camelCase column names verbatim. Result: on READ, `recurrenceId`/`scheduledAt`
/… silently bind **null** (String fields) or crash with the BUG-7
`ValueConversions` NPE (primitive fields). This was the real root cause of
the `schedules` NPE and of `history` printing `recurrence : null`.

Measured 01/10 — repro: `docs/repros/orm-camelcase/` (`myLabel` reads null,
`myCount` throws; the raw `db.query` proves the value is stored).

**Workaround (applied):** every persisted field is lower_snake_case
(`src/Store.kf`: `created_at`, `occurrence_key`, `interval_days`,
`recurrence_id`, `scheduled_at`, …). `tests/FakeLm.kf` pins the read path
(`history` must NOT print `recurrence : null`).

## BUG-7 — `json.decode` of missing/null PRIMITIVE record field throws the JDK binder NPE (OPEN)

`json.decode<T>` where T has a `Bool`/`Int`/… component and the JSON omits
the key (or sends `null`): `catch (String e)` receives the JDK-internal
message (`Cannot invoke "java.lang.Number.intValue()" because the return
value of "sun.invoke.util.ValueConversions.primitiveConversion(...)" is
null`) instead of an honest `missing field 'done' for Envelope`. Same
signature BUG-8 produces through the ORM. Repro:
`docs/repros/json-missing-primitive.kf` (build + run on
`kof-cli-0.5.0-beta.jar`). `KofLm.lmComplete` additionally pre-detects
`{"error":...}` envelopes (retired Ollama cloud models measured) so a
server error never reaches the binder.

## GAP-3 — no `kof.lm` in the stdlib (OPEN by design)

There is no language-model namespace; `KofLm.kf` is the minimal KofLM face
(kof.http + kof.json + config, OpenAI-style `/api/chat`, Ollama default).
Model availability is data (`lmAvailable()`), never an exception.

## GAP-4 — timezone default (docs vs runtime) (OPEN)

`timestring`/schedule parsing must refuse an unavailable IANA zone instead
of assuming UTC. `Recurrence.zoneOffsetHours` returns the sentinel `999999L`
for unknown zones; `Context.loadCompany` throws on `timezone: <unknown>`
("refusing to assume UTC"); `cli check` shows `RECUSA` for bad schedule
zones. `tests/Cli.kf` pins this against `Terra/Marte`.

## GAP-5 — `kof.http` verbs return the BODY only, no response headers (OPEN)

`get/post/put/patch/delete/options` return the body `String`; `status` is a
separate GET-only probe. The Posts API (`/rest/posts`) answers 201 with the
post id in the `x-restli-id` HEADER (empty body) — so reading a header is
mandatory unless the client sends `Prefer: return=representation` (which the
LinkedIn target now does). A header face (`http.postResp -> {status, headers,
body}`) would remove the trick; recorded as a stdlib gap.

## BUG-9 — `kof.secrets` doc promises `env KOF_<NAME> > config`; JVM impl is bare `System.getenv(name)` (REPRODUCED 02/10)

`learn/stdlib/secrets.md` shows `secrets.get("db_password")  // env KOF_DB_PASSWORD > config`.
Measured on the installed 0.5.0-beta runtime: `JvmStringSecurityRuntime.kof_sec_secret_get`
is literally `return System.getenv(name);` — NO `KOF_` prefix, NO config fallback.
Probe (env `KOF_LM_API_KEY` exported): `secrets.get("LM_API_KEY","")=0`,
`secrets.get("lm_api_key","")=0`, `config.env("KOF_LM_API_KEY")` sees 25 chars.
Either the doc lies or the impl is unfinished; the publisher now resolves
credentials through `config.str(...)` (which DOES honour KOF_ env mapping)
with the literal env name as fallback (`pSecret` in `src/Targets.kf`).
Candidate ledger: docs/impl divergence must be pinned by an executable test.

## BUG-10 — incremental `kof build` does not regenerate the JSON decode overlay for NEW record types (REPRODUCED 02/10)

Adding a new record used by `json.decode<T>()` (OaiResp) to a file already in
the build set, then `kof build src --target jvm`, produced classes whose
generated `dev/kof.runtime.KofRuntime` overlay still had the OLD decoder set
(56 `decode_*` methods, no `decode_OaiResp`) -> runtime `NoSuchMethodError:
KofRuntime.kof_json_decode_OaiResp` while `kof test` (fresh in-process
compile) passed the identical decode. `rm -rf build/classes && kof build`
regenerated the overlay (59 decoders) and the binary worked. The incremental
path must detect new decodable types (or always regenerate the overlay).
Workaround in use: full clean rebuild. (Same failure mode family as stale
build/classes noted on 01/10 — one root cause: overlay generation keyed off
the previous class set.)

## BUG-11 — direct `poll(h)` assign (sem cast) gera bytecode que não verifica (RESOLVIDO 02/10)

`raw = poll(h)` numa atribuição de String compila mas estoura no verifier na
PRIMEIRA carga da classe: `VerifyError: Bad type on operand stack ... Type
'java.lang/Object' not assignable to java/lang/String` (ou `not assignable to
integer` no `while (waited < N && !done(h))` do mesmo método). `poll` retorna
`Object`; a atribuição direta ao slot de String não emite `checkcast`.
Repro minimo em `docs/repros/poll-cast.kf` (mesma shape: class method +
spawn de funcao top-level + while `!doneH(h)` + `raw = poll(h)`): falha com
VerifyError; com `var v = poll(h); raw = v as String` (padrao ja usado em
KofLm) carrega e roda. Fix aplicado no `LinkedInTarget.publish`. Nota de
honestidade: o segundo suspeito (`Void checkAuthorPolicy() { ... return 0 }`)
foi trocado por `Int` por cautela, mas o repro minimo confirma o poll como
causa; os builds que ainda davam VerifyError depois do fix eram classes
compiladas ANTES dele (ver BUG-10, overlay velho).

## GAP-6 — Posts API refuses `urn:li:group:*` authors; `LinkedIn-Version` must be an active release date (MEDIDO 02/10)

Live probe against `https://api.linkedin.com/rest/posts` with a member token:
- `LinkedIn-Version: 202506`/`202610` -> 426 NONEXISTENT_VERSION ("20250601/
20261001 is not active"); `202609` is active.
- author `urn:li:group:40610004` -> 422: "author value ... is of type group.
Allowed URN types are organization, person". **LinkedIn groups cannot be
posted to via API**, even for the group owner; automation paths are member
or organization (Community Management, request under review). Documented
because the publisher's whole point is honest capability limits.

## Notes (not bugs)

- `config` precedence env `KOF_<KEY>` > `kof.config` — used by tests
  (`KOF_LM_URL=http://127.0.0.1:1` for the offline generate test).
- Thinking models: `qwen3.5:0.8b` on this box burns the WHOLE budget on
  `thinking` (empty `message.content`, or ~1.5 s/token CPU time) unless the
  request carries Ollama's `"think":false`. `KofLm` sends `think:false` by
  default (config `lm.think=true` to opt back in) — measured: small prompt
  without the flag did not answer in 120 s; with it, same model replied in
  44 s. HTTP timeout is SECONDS on `http.timeout` and it behaves as
  documented (KofLm's poll limit now uses the wall clock, not an
  accumulated 50 ms count).
- SQLite driver: `db.connect("jdbc:sqlite:...")` needs the sqlite-jdbc jar on
  the runtime classpath (`kof build` records the dep; standalone `java -cp`
  runs list it explicitly in README/tests).
