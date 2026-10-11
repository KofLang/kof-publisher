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
| `github.api` | `KOF_GITHUB_API` | base da API do GitHub (default `https://api.github.com`); os testes apontam pro fixture local |
| `github.token` | `KOF_GITHUB_TOKEN` | token **opcional** (só eleva o rate limit; leitura pública funciona sem ele) |
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

### Modo perfil pessoal (`examples/mel.kofmd`) — quatro horários, assistido
O mesmo motor editorial serve o **perfil pessoal**, sem duplicar pipeline. O
que muda é o KofMD: ele declara identidade, voz, temas, **opiniões
registradas**, **fatos conhecidos**, **princípios de engenharia**,
**categorias editoriais** e a **política editorial**.

- **Identidade em seções separadas** (§1): `# facts` (bio factual), `# opinions`
  (opiniões registradas), `# principles` (princípios de engenharia), `# topics`,
  `# avoid`, `# voice`/`guide` (voz, 24 pontos) e `# sources`. O prompt as
  mantém **separadas** e rotuladas: fato pode ser afirmado *dentro do que a
  fonte demonstra*; opinião pode ser desenvolvida mas **nunca** distorcida nem
  afirmada com mais certeza do que o material sustenta; princípio orienta o
  argumento, não é manifesto pra repetir.
- **Quatro horários como categorias flexíveis**: seções `# category <nome>`
  com `clock` (06:00/12:00/15:00/18:00), `label` e `angle`. O `clock` é a
  chave que liga o horário da agenda à categoria. As categorias são
  *orientação* (angulam o texto), **não** quatro obrigações de postar: se não
  houver material, o horário fica sem post.
- **Autenticidade por construção**: o prompt separa explicitamente
  **FATOS CONHECIDOS** (afirmáveis dentro do que a fonte demonstra),
  **OPINIÕES REGISTRADAS** (desenvolvíveis, nunca distorcidas) e **IDEIAS
  NOVAS** (só como raciocínio/hipótese, **nunca** como experiência vivida). As
  regras de `authenticity:` viram constraints duras no prompt.
- **Memória editorial** (`src/Memory.kf`): antes de gerar, o pipeline recebe
  os rascunhos vivos (review/approved/scheduled/published) e o validador
  **rejeita** abertura repetida e **avisa** conclusão parecida, além de barrar
  sobreposição lexical alta. Repetir um assunto é permitido; reapresentar o
  mesmo raciocínio como novidade não.
- **Gate de material**: `# editorial` com `require_material: true` e
  `max_chars: N`. Sem tópicos/opiniões/fatos ⇒ SKIP honesto, nada inventado.
- **`publisher plan`**: prepara **uma proposta por categoria** e as apresenta
  para revisão. Grava em `review` com alvo `dryrun` e **não publica nada** —
  a decisão de publicar fica com a autora (assisted).

```bash
# os quatro textos do dia, para revisão (não publica):
java -cp build/classes:$JARS Default.Main plan --company examples/mel.kofmd --store mel.db
# revisar / aprovar / publicar um deles quando quiser:
java -cp build/classes:$JARS Default.Main review  <id> --company examples/mel.kofmd --store mel.db
java -cp build/classes:$JARS Default.Main approve <id> --company examples/mel.kofmd --store mel.db
java -cp build/classes:$JARS Default.Main publish <id> --target dryrun --company examples/mel.kofmd --store mel.db
```

O agendamento reusa o mesmo scheduler (`# schedule <nome>` com `every: 1` e
`at: HH:MM`); no modo `assisted` o daemon gera e deixa em `review` sem
publicar. Ligar publicação automática é uma decisão posterior, não o default.

### Pesquisa online, seleção de pauta e memória editorial

O `plan` do perfil pessoal não inventa pauta: ele **pesquisa**, **pontua**,
**escolhe** e só então gera.

- **`src/Research.kf`** consulta fontes públicas reais (Hacker News via Algolia,
  dev.to, lobste.rs) e feeds RSS. Cada candidato carrega **url, veículo, data de
  publicação e data de consulta**; nada é inferido. Se uma fonte responde um
  erro em JSON, a leitura **falha honestamente** em vez de virar "zero itens"
  (um corpo `{"message": ...}` não é uma lista vazia). Google Trends **não** tem
  API gratuita (404 medido): a interface existe, o endpoint padrão é vazio, e o
  sistema **não** finge ter consultado.
- **Conteúdo externo é dado não confiável**: título e resumo passam pela mesma
  sanitização do GitHub (segredos redigidos, instruções neutralizadas). A
  mitigação de injeção **não** é garantia de fidelidade factual — por isso o
  material vai ao prompt com os **limites declarados** (ver abaixo).
- **`src/Planning.kf`** pontua cada candidato em quatro componentes
  **impressos por extenso** (atualidade, evidência, relevância, originalidade),
  nunca uma caixa-preta. A função editorial de cada horário vem do `function:`
  da categoria: `projetos` (o que mudou no repositório, sustentado na análise
  persistida), `noticias` (fonte consultada, com url e data), `contraponto`
  (posição própria contra um hype) e `observacao`.
- **Slots diferentes por construção**: o slot de `observacao` tira sua tese da
  lista `# rejects` (o que a autora **recusa**), não das `# opinions`. Duas
  opiniões sobre IA escolhidas em horários diferentes produziriam dois posts
  com a mesma tese — e a memória lexical **não** pega isso (medido: 0% de
  sobreposição de 4-gramas entre dois textos que diziam a mesma coisa). Lista
  diferente é o que separa de fato.
- **Limites declarados no material**, medidos na primeira rodada real: o slot de
  projeto recebe o *digest* da análise e é avisado de que **nada foi executado
  ali** ("há arquivos de teste" ≠ "os testes cobrem"); o slot de notícia recebe
  título, url, datas e o resumo da própria fonte, e é avisado de que **não leu o
  artigo** nem sabe a implementação; os slots de opinião recebem **só a posição**
  (sem episódio, sem dia, sem número) e são proibidos de narrar caso vivido.
- **Memória editorial em SQLite** (`src/Store.kf`): entidades `TopicRecord`
  (pauta) e `SourceRef` (fonte consultada), migração versionada por
  `orm.migrate` (com guarda de pragma, porque `CREATE TABLE IF NOT EXISTS` não
  altera tabela existente), **WAL**, `db-stats` (tamanho somando `.db` + `-wal`
  + `-shm`, integridade, contagens) e retenção (`db-prune`): ~10.000 registros,
  teto de disco de 20 GB como salvaguarda, limpeza **só** de registros
  terminais, do mais antigo primeiro, e **parada controlada de escrita** quando o
  teto é atingido sem espaço a liberar.
- **Validação factual é proxy mecânico, e assume isso**: rastreabilidade (url
  citada tem de ser fonte consultada), atualidade (notícia exige fonte datada
  dentro da janela), fidelidade (primeira pessoa só quando o material é da
  própria autora; narrar episódio ou alegar ter lido o artigo é **bloqueado**) e
  números (métrica tem de constar dos fatos ou da fonte). O texto do gate diz,
  em toda execução, que ele **não** decide se uma frase é verdadeira.

```bash
# o que as fontes estão dizendo agora (url + data de publicação e de consulta):
java -cp build/classes:$JARS Default.Main research --company examples/mel.kofmd --store mel.db
# o que o banco tem, quanto ocupa e se está íntegro:
java -cp build/classes:$JARS Default.Main db-stats --company examples/mel.kofmd --store mel.db
# aplicar a retenção (só registros terminais saem):
java -cp build/classes:$JARS Default.Main db-prune --company examples/mel.kofmd --store mel.db
```

## Projetos públicos no GitHub (fonte de conhecimento, só leitura)

O perfil pode declarar de onde vem conhecimento sobre os projetos da autora.
A seção `# github` é **explícita** — a conta **nunca** é adivinhada, porque o
nome da organização não é a conta pessoal da autora (§2.1):

```kofmd
# github
account: melmonfre          # conta PESSOAL, confirmada por evidência
enabled: true
orgs:
  - KofLang                 # organizações (identidades separadas)
```

`publisher github` (`src/Github.kf`) fala com a REST API v3 em modo
**somente leitura** — lista repos públicos, lê metadados, README, commits
recentes, releases e a raiz do repo. Nunca escreve, nunca faz push, nunca toca
repo privado, nunca guarda credencial.

- **Conta confirmada com evidência**: exige `type=User` **e** que o login
  apareça como contribuidor de um repo próprio. Login de organização, conta
  desconhecida, conta que nunca contribuiu ou falha de API ⇒ **recusa**, com o
  motivo, sem tratar os repos como se fossem dela.
- **Quatro níveis de alegação, mantidos separados** (§2.4): `[documentado]`
  (README/descrição), `[encontrado no codigo]` (linguagem, raiz, testes pelo
  nome), `[verificado aqui]` (só se **este** publisher executou build/testes —
  ler um README nunca promove a isso) e `[nao verificado]`. A ressalva viaja
  junto no prompt, então o modelo não pode alegar verificação que não houve.
- **Incremental com memória por repo** (§2.7): cada repo vira uma linha
  `RepoState` (digest + `pushed_at` + flags de verificação). Um repo sem
  mudança não é relido — economiza rate limit e evita que os fatos do projeto
  se movam em silêncio. `--force` reanalisa; `--limit N` limita o custo.
- **Sem virar feed de commits** (§2.11): a atenção é distribuída entre os
  projetos (o digest entra no material com no máximo 4 blocos, e a instrução
  diz pra variar de projeto em vez de correr atrás do último commit).
- **Segredos sanitizados** (§2.9): conteúdo lido de repo público passa por
  `secrets.redact` + prefixos de token (`ghp_`/`github_pat_`/`AKIA`/…) +
  redação de atribuições (`password:`/`api_key=`). Um token commitado por
  engano **nunca** é reproduzido no digest nem no relatório.

```bash
# analisa os projetos (somente leitura) e alimenta o próximo plan/generate:
java -cp build/classes:$JARS Default.Main github --limit 8 --company examples/mel.kofmd --store mel.db
# inspecionar exatamente o que foi aprendido (já sanitizado):
java -cp build/classes:$JARS Default.Main github --show --company examples/mel.kofmd --store mel.db
```

## Serviço: `start` / `stop` / `status`

O daemon recorrente pode ser operado como serviço em segundo plano
(`src/Service.kf`), reusando o daemon existente (ledger de ocorrência + STOP
file) — a CLI só adiciona o desprendimento e a checagem honesta de vida.

```bash
java -cp build/classes:$JARS Default.Main start  --company examples/mel.kofmd --store mel.db
java -cp build/classes:$JARS Default.Main status --company examples/mel.kofmd --store mel.db
java -cp build/classes:$JARS Default.Main stop
```

- **Desprendido**: `setsid -f` (sempre faz fork) põe o daemon numa sessão
  nova, então ele sobrevive ao terminal e `start` retorna na hora.
- **Sem duplicata**: um pid vivo que é *o nosso* daemon faz `start` recusar.
- **Vida confiável**: **pid file sozinho não é prova** — cada checagem confirma
  que o processo está vivo **e** é o nosso daemon (pelo `/proc/<pid>/cmdline`),
  então um pid reciclado nunca é morto por engano.
- **Stop gracioso**: escreve o STOP file que o daemon já honra, espera, e só
  então manda `SIGTERM` no **pid exato** (nunca `killall`). A fila, o ledger e
  o histórico são **preservados** — parar não é apagar.
- **Serviço ≠ autorização**: `status` reporta o estado do serviço e o estado
  editorial **separados**. Subir o serviço **não** vira `assisted` em
  `autonomous`: o `status` mostra `publicacao: ASSISTIDA` mesmo com o serviço
  ativo.


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
plan (uma proposta por categoria, assisted/dry-run, NAO publica)
list (--status) | review <id> | approve <id> | reject <id> <motivo> | cancel <id>
publish <id> [--target dryrun|clipboard|linkedin]
github (--limit N --repo owner/name --force --show)  le projetos publicos (so leitura)
research (--sources a,b --rss url --query q)  consulta as fontes atuais, com url + data
db-stats (registros por estado, pautas, fontes, tamanho, journal, integridade)
db-prune (--vacuum)  aplica a retencao (so remove registros terminais, mais antigos)
schedule (--name --days mon,wed --at 09:00 | --every N --anchor DATA) 
schedules | sync (importa blocos `# schedule <nome>` do KofMD)
daemon (agenda viva; STOP file em <publisher.home>/STOP) | history
start | stop | status (servico destacado: sobe, para com graca, reporta estado)
```
Flags globais: `--company <file>` `--store <db>`. Config (`KOF_<KEY>` >
`kof.config`): `lm.url|model|tokens|timeout|think|style|temp`,
`publisher.home|store|dryrun.dir`,
`linkedin.api|access.token|author.urn|allow.personal`, `github.api|token`.
LM: estilo `openai` autodetectado quando a URL contém `/v1` (beta-llm;
`reasoning_effort=none` senão o thinking come o budget), Ollama caso
contrário (`"think":false` por default pelo mesmo motivo).

## Testes — 77/77 verdes (kof instalado 0.5.0-beta e dev-jar)

```bash
rm -rf build/classes && kof build src --target jvm
kof test src/Recurrence.kf --target jvm                  # 6  calendario/timezone
kof test src/Model.kf --target jvm                       # 4  maquina de estados + loader
kof test src/Memory.kf --target jvm                      # 4  memoria editorial (lexical)
kof test tests/Cli.kf --target jvm --timeout 140         # 8  e2e CLI (binario real)
kof test tests/FakeLm.kf --target jvm --timeout 220      # 3  pipeline+LM fake+daemon
kof test tests/KofLab.kf --target jvm --timeout 260      # 4  fatos da lab+skip+estilo+marker
kof test tests/Personal.kf --target jvm --timeout 260    # 4  perfil pessoal: plan/categorias/repeticao/material
kof test tests/Identity.kf --target jvm --timeout 260    # 5  identidade: fatos/opinioes/principios no prompt, avoid, episodio inventado, alegacao de leitura
kof test tests/Github.kf --target jvm --timeout 300      # 12 github: evidencia/cache/sanitizacao/falha honesta
kof test tests/Service.kf --target jvm --timeout 300     # 4  start/stop/status (sem duplicata, preserva estado)
kof test tests/Targets.kf --target jvm --timeout 120     # 3  fronteira de publicacao (stub local; assisted nunca chama a API)
kof test tests/Research.kf --target jvm --timeout 200    # 12 pesquisa online + retencao/migracao do banco
kof test tests/Planning.kf --target jvm --timeout 300    # 8  selecao de pauta + integracao pesquisa->geracao->REVIEW
```
Os E2E sobem fixture HTTP (Ollama-compatible para o LM, REST v3 para o GitHub;
só o *modelo* e o *GitHub* são determinísticos; http/json/orm/targets/daemon/
process são reais). `KOF_LM_LIVE=<modelo>` roda o mesmo fluxo contra o LM de
verdade. Paths: `KOF_PUBLISHER_DIR|CLASSES`, `KOF_SQLITE_JAR`.

**Limite honesto da memória editorial**: a detecção de repetição é *lexical*
(abertura/conclusão + sobreposição de n-gramas), porque o runtime Kof não tem
busca semântica/embeddings. Isso pega "mesmas palavras apresentadas como
novidade"; **não** pega uma tese reformulada com outras palavras. Um check
semântico exigiria uma chamada de modelo que o projeto não orça hoje — o proxy
lexical é proporcional e a lacuna fica declarada, não escondida.

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
| interop `ProcessHandle`/`ManagementFactory` | `IncompatibleClassChangeError` no JVM (BUG-13); o pid do daemon vem de `sh -c 'echo $PPID'` |
| descoberta da conta GitHub | **só por configuração explícita** (`# github account:`); org ≠ conta pessoal da autora |
| "pesquisa na internet" | é uma **lista curada** de fontes (HN Algolia, dev.to, lobste.rs, RSS), não busca web geral; não existe busca geral gratuita |
| Google Trends | ❌ sem API gratuita (404 medido); interface pronta, endpoint padrão vazio — **não** se finge consultá-lo |
| RSS | extrator `<item>` artesanal (Kof não tem parser de XML), frágil por construção |
| fidelidade factual | **não** é garantível por validador mecânico: o gate é proxy e diz isso; a barreira real continua sendo a revisão humana (`assisted`) |
| originalidade entre slots | lexical (n-gramas). Dois textos com a mesma tese e palavras diferentes não são pegos; por isso os slots de opinião tiram tese de **listas diferentes**, não de um limiar de similaridade |
| modo de publicação | permanece `assisted`; **iniciar o serviço não autoriza publicação automática** |

## Estrutura

```
src/    Main Publisher Context Recurrence LabNews Editorial KofLm Store Scheduler
        Targets Model Github Service Memory kofmd/
tests/  Cli FakeLm KofLab Personal Identity Github Service
        fake_lm_server.py fake_lm_koflab.py fake_lm_personal.py fake_github.py
tools/  linked_oauth.py linked_oauth_page.py koflab-daily.sh
examples/ kof-lab.kofmd mel.kofmd         # empresa generica, lab, perfil pessoal
docs/   gaps-and-reports.md repros/          # bugs reais medidos, com minimo reproduzivel
var/    koflab.db koflab-daily.log           # runtime, nunca versionado
```

### Diário com o CM aprovado (destino final)
`tools/koflab-daily.sh` já está pronto: fetch `origin/lab` → generate (fatos
reais) → valida → `publish --target linkedin` com token/URN da página. Para
ligar de vez: `30 9 * * * /home/mel/Documentos/kof-publisher/tools/koflab-daily.sh >> .../var/koflab-daily.log 2>&1`.
