# kof-publisher

Editor e publicador recorrente do LinkedIn do **Kof**, escrito 100% em Kof
sobre a superfície real do Kof4j: KofMD (identidade editorial), KofTime
(recorrência com timezone IANA explícito), KofLM (chat Ollama/OpenAI-style
via `kof.http`+`kof.json`), `kof.orm` sobre SQLite (fila + ledger de
idempotência) e `kof.process` (git real, clipboard, daemon). Zero stubs:
quando o LM está fora, a CLI falha com a causa real, nunca finge sucesso.

Licença: **GPLv3** ([LICENSE](LICENSE)) — o pipeline é software livre e
qualquer uso derivado mantém a licença.

> **Estado em 02/10:** o pipeline completo funciona e o POST real na Posts
> API do LinkedIn foi validado (HTTP 201 no feed de membro). Publicar *como
> página* depende da aprovação do Community Management (em review, 10–14
> dias úteis). Grupos **não** têm API (o LinkedIn recusa `urn:li:group`).
> Enquanto o CM não sai, o fluxo diário usa o alvo `clipboard` (texto pronto
> pra colar na UI). Limitações e bugs abertos: [docs/gaps-and-reports.md](docs/gaps-and-reports.md).

## Configuração por usuário (multi-tenant, zero hardcode)

Toda configuração sensível ou de caminho vive em **`kof.config`** ou em
**env `KOF_<CHAVE>`** — precedência `KOF_CONFIG` > env > profile >
`kof.config` > default do código. Copie `tools/kof.config.example` e edite;
ou exporte os `KOF_*`. Nada de editar código para trocar usuário, LM,
destino ou repositório. Chaves principais:

| chave (kof.config) | env equivalente | o que faz |
|---|---|---|
| `lm.url` `lm.model` `lm.api.key` | `KOF_LM_*` | LM (auto-detecta OpenAI-compatível quando a URL tem `/v1`; senão Ollama) |
| `linkedin.author.urn` | `KOF_LINKEDIN_AUTHOR_URN` | `urn:li:organization:<id>` = **página** (requer CM aprovado) · `urn:li:person:<sub>` = **perfil**. GRUPO NAO EXISTE como author na Posts API (422 medido: "Allowed URN types are organization, person") |
| `linkedin.access.token` | `KOF_LINKEDIN_ACCESS_TOKEN` | token OAuth do app correspondente |
| `linkedin.allow.personal` | `KOF_LINKEDIN_ALLOW_PERSONAL` | `true` só quando o operador quer conscientemente postar no próprio perfil |
| `publisher.home/store/dryrun.dir` | `KOF_PUBLISHER_*` | onde vivem fila/ledger (default `$XDG_DATA_HOME/kof-publisher`) |
| (source_repo no .kofmd) | `KOF_KOF4J_REPO` | `source_repo: $KOF_KOF4J_REPO` — o loader expande `$VAR` no KofMD |

O destino é escolhido por configuração, **o mesmo código serve os dois
modos automáticos**: página (token/URN do Community Management) e perfil
(`allow.personal=true` como opt-in explícito). Sem caminhos hardcoded, sem
estado no repositório, sem etapa manual no meio.

## TL;DR — rodando hoje

```bash
cd /home/mel/Documentos/kof-publisher          # (ou o seu checkout)
rm -rf build/classes && kof build src --target jvm   # kof 0.5.0-beta
cp tools/kof.config.example ~/.config/kof/kof.config # edite: LM + URN + token
export KOF_KOF4J_REPO=/caminho/para/Kof4j             # ou edite source_repo no .kofmd

# ciclo completo, automatico:
tools/koflab-daily.sh   # fatos da lab -> LM -> validacao de estilo -> POST real
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

## Como configurar seu próprio app no LinkedIn

Quem clonar este repositório **precisa criar o próprio app no LinkedIn Developers**, pois nenhuma credencial é versionada:

1. Acesse [LinkedIn Developer Portal](https://developer.linkedin.com/) e faça login.
2. Clique em **Create App**:
   - Escolha o nome e associe a uma página ou crie um app standalone.
   - Faça upload de um logo qualquer (obrigatório pelo LinkedIn).
3. Na aba **Products**:
   - **Para postar no seu perfil (membro):** Adicione o produto **Share on LinkedIn** e **Sign In with LinkedIn using OpenID Connect**.
   - **Para postar como Página de Empresa:** Solicite acesso ao **Community Management API** (requer aprovação da equipe do LinkedIn, 10–14 dias úteis).
4. Na aba **Auth**:
   - Pegue seu `Client ID` e `Client Secret` (Primary Client Secret).
   - Na seção **OAuth 2.0 settings** -> **Authorized redirect URLs**, adicione:
     - `http://localhost:8737/callback` (se for usar o app de perfil/membro)
     - `http://localhost:8738/callback` (se for usar o app de página/Community Management)
5. Salve as chaves na sua máquina local (fora do git):
   ```bash
   mkdir -p ~/.local/share/kof
   cat <<EOF > ~/.local/share/kof/linkedin-credentials.properties
   client_id=SEU_CLIENT_ID
   client_secret=SEU_CLIENT_SECRET
   EOF
   chmod 600 ~/.local/share/kof/linkedin-credentials.properties
   ```
6. Faça o OAuth inicial:
   ```bash
   # Para postar no perfil pessoal:
   python3 tools/linked_oauth.py
   # Ou para postar como página (após aprovação do CM):
   python3 tools/linked_oauth_page.py 8738
   ```
   Abra a URL gerada no navegador, autorize na sua conta, e o script salvará o token e o URN em `~/.local/share/kof/linkedin-secrets.env`.

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
| Post real como membro | ✅ HTTP 201 validado ao vivo (via request direto; VerifyError da face `linkedin` resolvido (BUG-11: `poll(h)` sem cast); falta so o token CM pra postar de verdade pela Kof code) |
| Post como página | ⏳ aguardando CM (author `urn:li:organization` precisa escopo `w_organization_social`) |
| Post em grupo | ❌ sem API: `Allowed URN types are organization, person` (422 medido) |
| Versão da Posts API | header `LinkedIn-Version: 202609` ativo; 202506/202610 → 426 (medido) |
| native x86-64 | ❌ recusa honesta `JSN002` (record aninhado no encoder nativo) |
| JS | compila limpo; faces do publisher validadas só em JVM |
| `kof.secrets` | doc promete `KOF_`+config; JVM faz `getenv` puro (BUG-9) |
| build incremental | não regenera decoders de records novos (BUG-10) → sempre `rm -rf build/classes` |
| `poll(h)` sem cast | VerifyError na carga da classe (BUG-11, resolvido no publisher; repro em `docs/repros/poll-cast.kf`) |

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
