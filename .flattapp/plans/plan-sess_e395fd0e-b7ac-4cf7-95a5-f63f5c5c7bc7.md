# Plano — sistema editorial com pesquisa, memória e planejamento

## 1. Arquitetura encontrada (antes de mudar nada)

Kof 0.5.0-beta → JVM, pacote raiz plano, `Default.Main`.

- **`Store.kf`** é o único arquivo que toca o banco. Entidades na raiz (BUG-6), campos `snake_case` (BUG-8), timestamps ISO-8601 em String. Usa `orm.create/save/find/all/where/delete`. **Não existe** versionamento de schema, transação nem SQL cru em `src/`. `orm.all` não tem `ORDER BY` — o código depende da ordem de inserção.
- **`Context.kf`** parseia o KofMD num record `Company` (30 campos). `# sources` já é lido, mas **só renderizado no prompt — nunca buscado**.
- **`Editorial.kf`** = classe com `company` + `extraMaterial`; `validate` faz 14 checagens determinísticas (tamanho, travessão, CTA, avoid-list, repetição lexical). O material extra hoje só vem do GitHub.
- **`Github.kf`** é a única fonte HTTP externa, com a suíte de sanitização (`sanitizeSecrets`, `redactUrlCreds`, `neutralizeUntrusted`) e o padrão `spawn`+`done`+`poll`.
- **`Scheduler.kf`** = ledger de ocorrência + `runOccurrence` + `publishWithRetry`. **`Publisher.kf`** = 18 subcomandos. **`Targets.kf`** = destinos. **`Service.kf`** = ciclo do daemon.
- **Testes**: fixtures Python `http.server`, apontadas por env `KOF_*`, em HOME isolado, exercitando a CLI real.

**Capacidades medidas (decidem o desenho):**
- `orm.migrate(conn, nome, sql)` **existe** e é idempotente (cria `kof_migrations`) → dá versionamento.
- `db.execute(conn, sql, binds...)` e `db.query<T>` existem (máx. 4 binds) → dá VACUUM/PRAGMA/contagens.
- `File` tem `.exists/.readText/.writeText/.readBytes` — **não tem `.size()`** → tamanho via `process.run("stat","-c","%s",...)`, idiom já usado em `Service.kf`.
- HTTP devolve **só o corpo** (sem headers, sem status); **não há parser de XML/HTML** — só `json.decode<T>`.
- Fontes alcançáveis: **HN Algolia ✅, HN RSS ✅, dev.to ✅, lobste.rs ✅**; reddit ❌ 403; **Google Trends ❌ 404 (sem API gratuita)**.

## 2. Decisões

- **Trends**: não implemento scraping. Entrego a interface de "sinal de alta" pronta para um endpoint seu, e por padrão uso HN/dev.to/lobste.rs. É o que a própria especificação manda quando a fonte não está acessível.
- **RSS**: implemento com um extrator mínimo de `<item>` feito à mão (Kof não tem parser de XML), testável por fixture, documentado como frágil. Há precedente no repo (`ghPrivateRepoNames` varre corpo cru).
- **Modo**: permanece `assisted`. Nada será publicado.
- **Nada de** framework genérico, camada por operação, dump de página, dependência de IA nova, ou reescrita de módulo.

## 3. Fases (recomendo executar a Fase 1 e voltar para revisão)

### Fase 1 — Pesquisa + memória editorial (Partes 3 e 4)

**`src/Research.kf` (novo)**
- `record ResearchItem(topicKey, title, url, publisher, publishedAt, fetchedAt, summary, sourceType, score)` e `record ResearchOutcome(ok, items, error, detail)`.
- Clientes: `hnFrontPage()`, `hnSearch(q)`, `devToTop()`, `lobstersHot()`, `rssFeed(url)` — todos no padrão `spawn`+`done`+`poll`, devolvendo `ok=false` com erro honesto em falha/timeout/JSON ilegível.
- URLs base por `config.str("research.hn.api", …)` → sobrescrevíveis por `KOF_RESEARCH_HN_API` (é o gancho de teste).
- Títulos e resumos passam por `sanitizeUntrusted` — fonte pública é dado não confiável, como o README do GitHub.
- `researchAll(company)` agrega, deduplica por URL normalizada e capa por categoria.
- `trendsSignal()`: interface pronta, `ok=false` honesto enquanto não houver endpoint.

**`src/Store.kf`**
- Novas entidades: `TopicRecord` (pauta: id, topic_key, theme, argument, category, entities, researched_at, last_used_at, similarity_hash, status) e `SourceRef` (url_key, url, title, publisher, published_at, fetched_at, topic_id, summary, source_type).
- Ligação publicação↔pauta: `orm.migrate(conn, "publication-topic-id", "ALTER TABLE publication ADD COLUMN topic_id VARCHAR(255)")` — `CREATE TABLE IF NOT EXISTS` não altera tabela existente, então a migração é obrigatória e é exatamente para isso que ela serve.
- Retenção: `pruneByCount(limite)` (padrão 10.000 para posts+pautas, configurável), preservando `review`/`approved` e o recente; `pruneOrphans()` para fontes órfãs; limpeza em lotes; relata removidos e espaço liberado.
- Tamanho: `dbSizeBytes()` somando `.db` + `-wal` + `-shm` via `stat`; `vacuum()` por `db.execute`; **parada controlada de escrita** quando o teto (padrão 20 GB) for atingido e a limpeza não liberar espaço — preserva o que existe e informa, nunca apaga em massa.

**`src/Publisher.kf`**: subcomandos `research`, `db-stats` (posts por estado, pautas, tamanho, limite, última limpeza, removidos, integridade) e `db-prune`.

**Testes**: fixture Python servindo os JSONs e o RSS; `tests/Research.kf`; cobertura de retenção/migração/parada por limite via CLI.

### Fase 2 — Planejamento + as 4 funções editoriais (Partes 2 e 5)

- `# category` ganha `function:` (projetos | noticias | contraponto | observacao) e `sources:` opcional. Proponho manhã=projetos, meio-dia=noticias, tarde=contraponto, noite=observacao (o exemplo da especificação), ajustável por config.
- **`src/Planning.kf` (novo)**: `candidates()` (pesquisa + estados de repo do GitHub + fatos da lab), `score()` simples e transparente (atualidade, relevância, evidência, originalidade, diversidade), `selectFour()`, `persistPlan()`, `recentAvoid()`. Sem sistema de pontuação sofisticado.
- `plan` reescrito: pesquisa → seleciona → persiste pautas → gera por função → valida → **REVIEW**. Se faltarem pautas com qualidade, gera menos e sinaliza — não fabrica para preencher o horário.
- O post de projetos só usa evidência real e recente; repo sem atividade não vira novidade.

### Fase 3 — Perfil editorial + validação (Partes 1 e 6)

- `examples/mel.kofmd` ampliado para perfil **operacional**: como penso, como construo argumento, voz, regras de escrita, e a regra de evidência (documentado ≠ encontrado ≠ verificado ≠ testado). É conteúdo, não código.
- Novas chaves em `# editorial`: `research`, `research_max_age_hours`, `retention_records`, `retention_max_gb`.
- `validate` ganha checagens mecânicas: **rastreabilidade** (afirmação factual precisa de `SourceRef` existente), **atualidade** (data de publicação registrada; notícia velha não passa como nova), **fidelidade por proxy** (primeira pessoa sem evidência → problema; métrica numérica sem fato registrado → problema).
- **Limitação declarada**: isso é proxy mecânico, não garantia. Foi medido na auditoria (AUD-1) que o validador determinístico não consegue julgar fidelidade factual. O gate real continua sendo `assisted`.

### Fase 4 — Testes (Parte 7)

Os 20 cenários pedidos + o teste de integração pesquisa → seleção → geração → validação → REVIEW, com fixtures determinísticas.

## 4. Arquivos que pretendo tocar

Novos: `src/Research.kf`, `src/Planning.kf`, `tests/Research.kf`, `tests/Planning.kf`, fixtures Python de pesquisa.
Alterados: `src/Store.kf`, `src/Context.kf`, `src/Editorial.kf`, `src/Publisher.kf`, `src/Scheduler.kf`, `examples/mel.kofmd`, `README.md`.

## 5. Riscos e limites honestos

- **Não existe busca web geral gratuita.** Vou documentar isso: a pesquisa é uma lista curada de fontes, não "a internet".
- **Trends não implementado** (404 medido). Interface pronta, sem scraping frágil.
- **RSS é frágil** por construção (extrator artesanal).
- **Fidelidade factual não é garantível** por validador mecânico.
- **Ambiente offline** faz a pesquisa falhar — e ela vai falhar honestamente, sem fingir.
- Preservo integralmente as alterações não commitadas do working tree. Sem commit, sem push, sem publicação, sem `autonomous`.

## 6. Ordem de execução

Começo pela Fase 1, rodo a suíte completa (hoje 55 testes verdes) e volto com o resultado antes de seguir para a Fase 2.