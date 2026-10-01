# Gaps & bug reports measured while building kof-publisher

Environment: kof 0.5.0-beta (installed `kof`) and `kof-cli-0.5.0-beta.jar`
built from the current tree — both tested on OpenJDK 25 (Temurin), Linux.
"installed" and "dev-jar" below refer to those two binaries. Repros in
`docs/repros/`.

## BUG-6 — ORM entity in a named package: class descriptor without package (OPEN, both binaries)

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

## Notes (not bugs)

- `config` precedence env `KOF_<KEY>` > `kof.config` — used by tests
  (`KOF_LM_URL=http://127.0.0.1:1` for the offline generate test).
- Thinking models (qwen3.5:0.8b measured) return EMPTY
  `message.content` when the token budget is consumed by `thinking` —
  `lm.tokens` must be large (>= 2000) or the response is empty-but-valid;
  `KofLm.lmComplete` surfaces empty content as `ok=false` with the real
  error text, never a crash.
- SQLite driver: `db.connect("jdbc:sqlite:...")` needs the sqlite-jdbc jar on
  the runtime classpath (`kof build` records the dep; standalone `java -cp`
  runs list it explicitly in README/tests).
