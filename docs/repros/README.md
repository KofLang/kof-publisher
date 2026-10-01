# Repros

| File | Shows | Binary |
|------|-------|--------|
| `generic-return.kf` | top-level nested-generic return → PARSE075 | installed `kof` (dev jar: compiles) |
| `orm-entity-package/` | entity in a named package → `NoClassDefFoundError: Erec` | both |
| `nullable-primitive.kf` | `Int?` top-level return → NOT reproducible (measured OK 01/10) | — |
| `json-missing-primitive.kf` | `json.decode` of missing/null primitive field → JDK binder NPE message (BUG-7) | both |
| `orm-camelcase/` | ORM read lowercases labels → camelCase entity fields bind null (BUG-8) | both |
