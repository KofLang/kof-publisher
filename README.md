# kof-publisher

Editor e publicador recorrente do LinkedIn do **Kof**, escrito 100% em Kof
sobre a superfície real do Kof4j: KofMD (identidade editorial), KofTime
(recorrência com timezone IANA explícito), KofLM (chat Ollama/OpenAI-style
via `kof.http`+`kof.json`), `kof.orm` sobre SQLite (fila + ledger de
idempotência) e `kof.process` (git real, clipboard, daemon). Zero stubs:
quando o LM está fora, a CLI falha com a causa real, nunca finge sucesso.

> **Estado em 02/10:** o pipeline completo funciona e o POST real na Posts
> API do LinkedIn foi validado (HTTP 201 no feed de membro). Publicar *como
> página* depende da aprovação do Community Management (em review, 10–14
> dias úteis). Grupos **não** têm API (o LinkedIn recusa `urn:li:group`).
> Enquanto o CM não sai, o fluxo diário usa o alvo `clipboard` (texto pronto
> pra colar na UI). Limitações e bugs abertos: [docs/gaps-and-reports.md](docs/gaps-and-reports.md).

## TL;DR — rodando hoje

```bash
# 1. compilar (kof 0.5.0-beta; SEMPRE rebuild limpo apos mudar records — BUG-10)
cd /home/mel/Documentos/kof-publisher
rm -rf build/classes && kof build src --target jvm

# 2. definir o runbook alias CP para nao repetir o classpath
CP="build/classes:$HOME/.local/share/kof/lib/kof.jar:$HOME/.kof/deps/org/xerial/sqlite-jdbc/3.53.4.0/sqlite-jdbc-3.53.4.0.jar"
alias kpub="java -cp $CP Default.Main"

# 3. gerar o post do dia a partir dos FATOS da lab do Kof4j
source ~/.local/share/kof/kof-lm.env          # LM (beta-llm ou Ollama)
kpub generate --company examples/kof-lab.kofmd --store var/koflab.db \
              --topic "novidades da lab"

# 4. ver, aprovar, publicar
kpub list --company examples/kof-lab.kofmd --store var/koflab.db
kpub review <id> ...                           # mostra texto + validação
kpub approve <id> ...
kpub publish <id> --target clipboard ...       # interim: cola no grupo/página pela UI
```

## Os dois modos

### Modo empresa genérica (`init`)
`kpub init --company company.kofmd` cria o template KofMD (nome, tom,
tópics, agenda) e o pipeline editorial padrão (generate → review → approve →
publish), com aprovação humana (`assisted`) por default.

### Modo KOF Lab (`examples/kof-lab.kofmd`) — diário, automático
Todo dia às 09:30 (America/Sao_Paulo) o publisher posta **o que realmente
entrou na branch `lab` do repositório Kof4j**, na voz da autora:

- **Fatos, não vibes** (`src/LabNews.kf`): `git log` da janela (commits
  `feat/fix/docs`), bugs `§NNN` abertos no ledger, a última decisão `## D-`
  do DECISIONS.md, o que as lanes claimam no DOING.md. Janela = desde a
  última publicação BEM-SUCEDIDA (arquivo `lab-last.txt` no `publisher.home`).
  Dia sem novidade ⇒ "sem novidades", **nada é publicado** e a janela do
  dia seguinte cobre os dois dias. O post nunca inventa fato.
- **Estilo é lei, não sugestão**: os 24 pontos do guia da autora vivem no
  `guide:` do KofMD e viram as system rules do LM; o validador determinístico
  **bloqueia** travessão, CTA genérico ("comenta aqui embaixo"), frase de
  coach, abertura artificial ("você já parou pra pensar"), abuso de
  dois-pontos e paragrafação picotada. Texto reprovado não passa.

## Credenciais (nunca no repositório)

| Arquivo (chmod 600) | Conteúdo |
|---|---|
| `~/.local/share/kof/linkedin-credentials.properties` | `client_id`/`client_secret` do app de membro |
| `~/.local/share/kof/linkedin-page-credentials.properties` | idem, app do Community Management |
| `~/.local/share/kof/linkedin-secrets.env` | `KOF_LINKEDIN_ACCESS_TOKEN` + `KOF_LINKEDIN_AUTHOR_URN` (refazer a cada ~60 dias) |
| `~/.local/share/kof/kof-lm.env` | `KOF_LM_URL/MODEL/API_KEY` do beta-llm (ou aponte pro Ollama local) |

Regras: segredo só via env/config (`pSecret`: `config.str` honrando `KOF_*`,
fallback `secrets.get` — a doc do `kof.secrets` mente sobre o prefixo, BUG-9);
nenhum token vai pra log (erros passam por `secrets.redact`); se um segredo
apareceu num chat, gire no portal.

### OAuth (uma vez por ~60 dias)
```bash
python3 tools/linked_oauth.py        # app membro: redirect http://localhost:8737/callback
python3 tools/linked_oauth_page.py 8738   # app pagina: redirect ...:8738, escopo w_organization_social
```
O script abre um listener local, você autoriza no Firefox logada, e ele grava
token (+ URN) no arquivo 600 correspondente. O token da página exige o CM
aprovado; sem ele, qualquer URN de organização volta 403. **Guarda de
segurança:** o `LinkedInTarget` recusa URN de perfil pessoal a menos de
`KOF_LINKEDIN_ALLOW_PERSONAL=true` conscientemente — um cron mal configurado
nunca posta na sua conta sem você querer.

## Comandos da CLI

```
init | check | generate (--topic, --ideas N, --publish-ok, --target)
list (--status) | review <id> | approve <id> | reject <id> <motivo> | cancel <id>
publish <id> [--target dryrun|clipboard|linkedin]
schedule (--name --days mon,wed --at 09:00 | --every N --anchor DATA) 
schedules | sync (importa blocos `# schedule <nome>` do KofMD)
daemon (agenda viva; STOP file em <publisher.home>/STOP) | history
```
Flags globais: `--company <file>` `--store <db>`. Config (`KOF_<KEY>` >
`kof.config`): `lm.url|model|tokens|timeout|think|style|temp`,
`publisher.home|store|dryrun.dir`, `linkedin.api|access.token|author.urn|allow.personal`.
LM: estilo `openai` autodetectado quando a URL contém `/v1` (beta-llm;
`reasoning_effort=none` senão o thinking come o budget), Ollama caso
contrário (`"think":false` por default pelo mesmo motivo).

## Testes — 24/24 verdes (kof instalado 0.5.0-beta e dev-jar)

```bash
rm -rf build/classes && kof build src --target jvm
kof test src/Recurrence.kf --target jvm                  # 6  calendario/timezone
kof test src/Model.kf --target jvm                       # 3  maquina de estados
kof test tests/Cli.kf --target jvm --timeout 140         # 8  e2e CLI (binario real)
kof test tests/FakeLm.kf --target jvm --timeout 220      # 3  pipeline+LM fake+daemon
kof test tests/KofLab.kf --target jvm --timeout 260      # 4  fatos da lab+skip+estilo+marker
```
Os E2E sobem fixture HTTP Ollama-compatible (só o *modelo* é determinístico;
http/json/orm/targets/daemon são reais). `KOF_LM_LIVE=<modelo>` roda o mesmo
fluxo contra o LM de verdade. Paths: `KOF_PUBLISHER_DIR|CLASSES`,
`KOF_SQLITE_JAR`.

## Idempotência (aceitação §12/§13)

Uma ocorrência = `(agenda, instante)`, chave determinística reivindicada no
ledger `Occurrence` **antes** de gerar. Restart, segundo daemon, retry ou
race nunca publicam a mesma coisa duas vezes. Publish que falhou reusa o
MESMO rascunho (nunca regenera texto diferente pro mesmo slot). Um `201` da
Posts API com corpo vazio conta como sucesso (o id so existe no header
`x-restli-id`, que o `kof.http` nao le — GAP-5) justamente pra o retry nao
duplicar um post que ja subiu ao vivo.

## Limites honestos (medidos, com repro em docs/)

| Coisa | Estado |
|---|---|
| Post real como membro | ✅ HTTP 201 validado ao vivo (via request direto; alvo `linkedin` do Kof tem o VerifyError BUG-11 aberto — a face nunca carregou numa E2E ate hoje) |
| Post como página | ⏳ aguardando CM (author `urn:li:organization` precisa escopo `w_organization_social`) |
| Post em grupo | ❌ sem API: `Allowed URN types are organization, person` (422 medido) |
| Versão da Posts API | header `LinkedIn-Version: 202609` ativo; 202506/202610 → 426 (medido) |
| native x86-64 | ❌ recusa honesta `JSN002` (record aninhado no encoder nativo) |
| JS | compila limpo; faces do publisher validadas só em JVM |
| `kof.secrets` | doc promete `KOF_`+config; JVM faz `getenv` puro (BUG-9) |
| build incremental | não regenera decoders de records novos (BUG-10) → sempre `rm -rf build/classes` |

## Estrutura

```
src/    Main Publisher Context Recurrence LabNews Editorial KofLm Store Scheduler Targets Model kofmd/
tests/  Cli FakeLm KofLab fake_lm_server.py fake_lm_koflab.py
tools/  linked_oauth.py linked_oauth_page.py koflab-daily.sh
docs/   gaps-and-reports.md repros/          # bugs reais medidos, com minimo reproduzivel
var/    koflab.db koflab-daily.log           # runtime, nunca versionado
```

### Diário com o CM aprovado (destino final)
`tools/koflab-daily.sh` já está pronto: fetch `origin/lab` → generate (fatos
reais) → valida → `publish --target linkedin` com token/URN da página. Para
ligar de vez: `30 9 * * * /home/mel/Documentos/kof-publisher/tools/koflab-daily.sh >> .../var/koflab-daily.log 2>&1`.
