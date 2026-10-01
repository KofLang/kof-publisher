# Repros

| File | Shows | Binary |
|------|-------|--------|
| `generic-return.kf` | top-level nested-generic return → PARSE075 | installed `kof` (dev jar: compiles) |
| `orm-entity-package/` | entity in a named package → `NoClassDefFoundError: Erec` | both |
| `nullable-primitive.kf` | `Int?` top-level return → check first (both jars measured OK 01/10) | — |
