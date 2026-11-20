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

### Modo perfil pessoal (`examples/mel.kofmd`) — dois horários, só atualização de repositórios
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
- **Dois horários, função única `projetos`**: seções `# category <nome>` com
  `clock` (06:00 e 17:00), `label`, `angle` e **`function: projetos`**. O
  `clock` é a chave que liga o horário da agenda à categoria. Com **todas** as
  categorias em `projetos`, o `plan` **dispensa a pesquisa de notícias**
  (imprime o motivo) e o pool de pautas vira apenas o estado dos repositórios
  das orgs declaradas em `# github` (`orgs: KofLang, Rede-ENois`) — o repo com
  `pushed_at` mais recente vira o post das 06:00, e o segundo org distinto o
  das 17:00. Repos pessoais não entram; cada slot tira um projeto diferente.
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
# os dois textos do dia, para revisão (não publica):
java -cp build/classes:$JARS Default.Main plan --company examples/mel.kofmd --store mel.db
# revisar / aprovar / publicar um deles quando quiser:
java -cp build/classes:$JARS Default.Main review  <id> --company examples/mel.kofmd --store mel.db
java -cp build/classes:$JARS Default.Main approve <id> --company examples/mel.kofmd --store mel.db
java -cp build/classes:$JARS Default.Main publish <id> --target dryrun --company examples/mel.kofmd --store mel.db
```

O agendamento reusa o mesmo scheduler (`# schedule <nome>` com `every: 1` e
`at: HH:MM`); no modo `assisted` o daemon gera e deixa em `review` sem
publicar. Ligar publicação automática é uma decisão posterior, não o default.

#### Personalidade: a autora escreve, não um "agente editorial"

O perfil pessoal declara **quem escreve** em seções próprias (`# background`,
`# values`, `# personality`, `# emotional_profile`, `# language`,
`# strong_language`, `# technical_domains`, `# editorial_engine`, `# review`,
`# restrictions`). O código não aplica isso como filtro no fim: a identidade é
o **system prompt**, e a emoção de cada post é **derivada do perfil** antes de
gerar, sem chamada de IA.

- **Escala 0-5** (`emotional_profile.levels`): cada nível tem nome e direção.
  O nível de um post vem do domínio do assunto, dos gatilhos declarados em
  `emotional_profile.states` e do piso da função do horário. Linguagem forte
  só é liberada a partir de `strong_language.levels`.
- **Diretiva visível**: `plan` e `samples` imprimem
  `DIRETIVA: dominio=… base=… emocao=… nivel=… formato=… funcao=…` e, na linha
  seguinte, `DIRETIVA> angulo proprio: …`, para você conferir *por que* o texto
  saiu irritado, curioso ou neutro e por onde a voz dela entra.
- **Um pouco dela em todo post** (`# signature motifs`): ângulos que ela traz a
  qualquer assunto, escolhidos um por post (inclusive em nível 0) e usados como
  critério, não como frase de efeito. Ausência gera aviso de "post genérico".
- **Motivo de existir**: as `editorial_engine.questions` vão no prompt; se a
  pauta não responde às duas primeiras, o modelo responde `SKIP:` e nada é
  gravado. Pauta vazia ou só de conectivos também é recusada.
- **Revisão que não amacia**: a reescrita é instruída a corrigir só o que a
  validação apontou, mantendo voz, intensidade e ponto de vista.
- **Anti-clichê**: estruturas declaradas em `language.cliche_structures`
  (ex.: "não é sobre X, é sobre Y") reprovam o texto; muletas de influenciador
  ("recentemente", "tenho pensado", "fiquei pensando") geram aviso e viram
  problema se já apareceram no histórico.

```bash
# 25 cenários de personalidade, N amostras cada, SEM gravar e SEM publicar:
java -cp build/classes:$JARS Default.Main samples \
  --scenarios examples/amostras.kofmd --runs 2 \
  --company examples/mel.kofmd --store mel.db
```

`samples` roda os **dois** gates do pipeline real (validação mecânica e
barreira de fidelidade factual) e imprime diretiva, veredito e texto de cada
amostra. As decisões de projeto estão em
[`docs/personalidade.md`](docs/personalidade.md); amostras reais antes/depois
em [`docs/amostras/`](docs/amostras/).

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
- **Cada horário faz a pesquisa completa**: quando o perfil declara `# category`
  (o caso do perfil pessoal), o daemon roda o **mesmo pipeline do `plan`** em
  cada ocorrência — consulta as fontes atuais, escolhe a pauta da função
  daquele horário, grava a pauta e as fontes, gera, valida (editorial + proxy
  factual) e deixa em `review`. Uma fonte que falha vira nota no log e o
  horário é **pulado**, nunca preenchido com notícia inventada. Sem `# category`
  (KofLab), o caminho antigo continua igual.


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

## Testes — 129/129 verdes (kof instalado 0.5.0-beta e dev-jar)

```bash
rm -rf build/classes && kof build src --target jvm
kof test src/Recurrence.kf --target jvm                  # 6  calendario/timezone
kof test src/Model.kf --target jvm                       # 4  maquina de estados + loader
kof test src/Memory.kf --target jvm                      # 4  memoria editorial (lexical)
kof test src/Thesis.kf --target jvm                      # 5  memoria editorial (semantica: assinatura + polaridade)
kof test tests/Cli.kf --target jvm --timeout 140         # 8  e2e CLI (binario real)
kof test tests/FakeLm.kf --target jvm --timeout 220      # 3  pipeline+LM fake+daemon
kof test tests/KofLab.kf --target jvm --timeout 260      # 4  fatos da lab+skip+estilo+marker
kof test tests/Personal.kf --target jvm --timeout 260    # 4  perfil pessoal: plan/categorias/repeticao/material
kof test tests/Identity.kf --target jvm --timeout 260    # 7  identidade: fatos/opinioes no prompt, avoid, episodio inventado, alegacao de leitura, acao em primeira pessoa
kof test tests/Github.kf --target jvm --timeout 300      # 12 github: evidencia/cache/sanitizacao/falha honesta
kof test tests/Service.kf --target jvm --timeout 600     # 9  start/stop/status (sem duplicata, preserva estado, daemon pesquisa, retentativa, geracao antecipada, falha do LM nao derruba o processo e o horario e retentado ate publicar)
kof test tests/Targets.kf --target jvm --timeout 300     # 4  fronteira de publicacao (stub local; assisted nunca chama a API; autonomo+perfil pessoal publica 1x e nao persiste o token)
kof test tests/Research.kf --target jvm --timeout 200    # 12 pesquisa online + retencao/migracao do banco
kof test src/Enois.kf --target jvm                       # 7  cliente do enois (url publica, html->texto, entidades, espacos, css/script)
kof test tests/Mirror.kf --target jvm --timeout 600       # 4  espelho: linha de base, post novo->link+legenda, sem texto, PAGE pelo detalhe
kof test tests/Planning.kf --target jvm --timeout 300    # 17 selecao + integracao + propriedade/ausencia/reacao/episodio/teste/build nao afirmados
kof test tests/Adversarial.kf --target jvm --timeout 300 # 19 cenarios: A-P (titulo so, produto, feature futura, tese repetida, tese oposta, sem fonte, sem data, plausivel sem evidencia, falha apos retries) + paragrafos, repo distinto, frase partida, assinatura Kof (com/sem), candidato de observacao nao recusado por boilerplate, "compilador" nao e "compila", noticia so com manchete (rejeitada no rascunho e fora do pool), assunto em cooldown nao volta
```
Os E2E sobem fixture HTTP (Ollama-compatible para o LM, REST v3 para o GitHub;
só o *modelo* e o *GitHub* são determinísticos; http/json/orm/targets/daemon/
process são reais). `KOF_LM_LIVE=<modelo>` roda o mesmo fluxo contra o LM de
verdade. Paths: `KOF_PUBLISHER_DIR|CLASSES`, `KOF_SQLITE_JAR`.

**Memória editorial em duas camadas.** A camada *lexical* (`src/Memory.kf`)
compara abertura/conclusão e n-gramas: pega "mesmas palavras apresentadas como
novidade". A camada *semântica* (`src/Thesis.kf`) compara a **tese** — palavras
de conteúdo dobradas por sinônimos, sem stopwords, com detecção de polaridade —
para pegar a tese reformulada com outras palavras. A assinatura fica gravada em
`topicrecord.thesis_signature` (migração 002) e a comparação roda **antes da
geração** (pauta repetida é recusada, não só penalizada).

**Limite honesto que permanece:** a camada semântica é determinística e por
isso ainda não pega duas teses que usem vocabulário *genuinamente* diferente
("complexidade acidental" vs "overengineering"). Ela também não normaliza
conjugação verbal. A adjudicação por modelo existe como opção explícita
(`--thesis-lm`), desligada por padrão, e sua lacuna fica declarada.

## Base de conhecimento dos repositorios (refresh agendado)

O daemon **nao** consulta o GitHub sozinho: ele le o que o comando `github` ja
persistiu na tabela `repostate`, e essa analise e **incremental** (um repo cujo
`pushed_at` nao mudou nao e relido). Sem uma atualizacao periodica, o slot das
**06:00** (trabalho real e projetos) enxerga o retrato do dia anterior.

`tools/github-refresh.sh` faz essa atualizacao. Ele roda **antes das 06:00** e
**nao publica nada** — o comando e somente leitura.

```bash
# cron (instalado nesta maquina, 05:30 diario)
30 5 * * * /home/mel/Documentos/kof-publisher/tools/github-refresh.sh >> ~/.kof/publisher/github-refresh.log 2>&1
```

Tambem ha um template systemd para quem prefere timer de usuario:
`tools/systemd/kof-github-refresh.{service,timer}` (05:30, `Persistent=true`).

O token vem de `~/.local/share/kof/github-secrets.env` (chmod 600) e, na falta
dele, de `gh auth token`. O script resolve o binario `java` explicitamente —
sob o PATH minimo do cron (`/usr/bin:/bin`) o `java` do sdkman nao existe
(medido), e o job falharia em silencio.

## Espelho do enois (modo alternativo, DESLIGADO)

**2026-10-17:** o publisher passou a espelhar o **perfil do autor no enois**
(`enois.ia.br/perfil/aminadojava`) em vez de publicar por horario. Em
**2026-11-01** o autor pediu a volta do modelo anterior, e o modo ativo voltou a
ser o de **publicacoes programadas** (06/12/15/18). O espelho nao foi removido:
continua no codigo e testado, desligado por padrao
(`publisher.enois.poll.min = 0`). Religado, o daemon faz o seguinte a cada
`publisher.enois.poll.min` minutos:

1. le os posts recentes do perfil (`GET /api/users/{id}/posts`);
2. ve quais sao **novos** (ledger `enoisseen` no SQLite — um post nunca e
   compartilhado duas vezes, e um daemon reiniciado continua de onde parou);
3. le o texto do post (para posts `PAGE`, o texto so vem no endpoint de detalhe,
   dentro de `pageHtml` — o cliente busca);
4. escreve uma **legenda** a partir do proprio texto do post;
5. compartilha o **link publico** do post (`/post/<id>`) no LinkedIn, com a
   legenda, via `content.article` (o LinkedIn monta o cartao do link).

```
kof.config / env            default
enois.username              (obrigatorio)
enois.site                  https://enois.ia.br
publisher.enois.poll.min    0     (0 = desligado; 10 religa o espelho)
publisher.enois.min.chars   40    (post curto demais nao tem o que legendar)
publisher.enois.max.per.poll 2    (no maximo 2 compartilhamentos por ciclo)
publisher.enois.limit       20    (quantos posts recentes ler)
```

### Tres regras que valem a pena saber

- **A primeira execucao so marca a linha de base.** Num ledger vazio todo post
  pareceria novo e o LinkedIn receberia uma rajada de posts antigos. O primeiro
  ciclo registra o que ja existe como visto e **nao publica nada**; a partir dai
  so post escrito depois vira compartilhamento. (`publisher.enois.backfill=true`
  forca o contrario, conscientemente.)
- **Nada e inventado.** A legenda sai do texto do post e o post e a fonte. Post
  sem texto legivel e **ignorado** e registrado como tal — nunca legendado por
  imaginacao.
- **Ordem cronologica.** Se um ciclo achar mais de um post novo, eles saem do
  mais antigo para o mais novo.

Comandos:

```
publisher mirror --company examples/mel.kofmd --store <db>          # um ciclo
publisher mirror ... --dry    # mostra o que sairia, sem publicar nada
```

### Fixtures com data RELATIVA (a suite nao pode envelhecer)

As fixtures de pesquisa e de GitHub tinham datas literais (`2026-10-10T12:00:00Z`).
O publisher descarta material mais velho que `research_max_age_hours` (168h nos
perfis de teste), entao a suite passava numa semana e comecava a falhar sozinha
na seguinte — em 2026-10-17, 9 das 11 datas ja tinham passado da janela e o
Planning caiu de 17/17 para 6/17 sem nenhuma mudanca de codigo. Agora cada data
e calculada a partir do AGORA (`iso_ago`), preservando a ordem e a distancia
relativa, e **memoizada por valor**: o fixture responde a MESMA data em toda
requisicao. Sem a memoizacao o instante era recalculado a cada request, o
`pushed_at` mudava entre duas execucoes e a cache de repositorios nunca via "sem
mudanca" (o teste de cache pegou exatamente isso).

Faltou o outro lado: o teste de Research continuava afirmando a data literal
`2026-10-10T12:00:00Z` de um item, que a fixture relativa nunca mais produziria.
Era diagnosticado como "falha intermitente sob carga", mas falhava sempre. A
assercao agora verifica que as DUAS datas (publicacao e consulta) vem presentes
e em ISO-8601 — o que o teste precisa provar — em vez do instante exato.

### As agendas por horario estao ATIVAS de novo

Os quatro horarios (06/12/15/18) estavam cancelados desde 2026-10-17, quando o
espelho do enois virou o gatilho. Em **2026-11-01** os blocos `# schedule`
voltaram para `examples/mel.kofmd`, `publisher sync` os reativou e o espelho foi
desligado (`KOF_ENOIS_POLL_MIN=0`). O motor de agenda nunca saiu do codigo nem
da suite.

Uma armadilha corrigida nessa volta: `register`/`sync` calculava a proxima
ocorrencia a partir de `created_at`, ou seja, o PRIMEIRO horario depois que a
agenda nasceu. Reativando uma agenda de dias atras isso caia no passado, e o
laco do daemon trata qualquer `next` passado como VENCIDO — um `sync` com o
daemon rodando dispararia os quatro horarios de uma vez. Agora um `next` futuro
so e preservado quando a definicao (clock/days/every/anchor) nao mudou (para nao
perder uma retentativa do dia); caso contrario ele e recalculado a partir de
AGORA.

## Cooldown de ASSUNTO (nao falar de IA todo dia)

A comparacao de tese decide se o ARGUMENTO e novo. Falta um nivel acima: o
**assunto**. Tres posts sobre IA podem defender coisas diferentes e ainda assim
ser "IA de novo" — foi a reclamacao do autor em 2026-10-13 ("nao da pra ficar
falando de ia todo dia"). O gate de tese nao via isso porque "ia" tem 2 letras e
era descartado da assinatura, e porque as tres opinioes de IA usam palavras
diferentes.

O perfil declara a taxonomia em `# editorial subjects`:

```
subjects:
  - ia: IA, llm, modelo, modelos, generativa, prompt, tokens, alucinacao
  - arquitetura: arquitetura, microsservico, monolito, distribuido
  - legado: legado, cobol, mainframe, z/os
  ...
```

O nome antes dos dois-pontos e o rotulo que aparece no relatorio; as palavras
disparam o assunto. Um assunto usado nos ultimos **4** itens editoriais
(`publisher.subject.window`, 0 desliga) nao e escolhido de novo — com 4 posts
por dia, isso significa "nao dois dias seguidos". A sigla **IA** e casada
**preservando maiusculas**, senao "eu ia fazer" contaria como o assunto.

Quando um slot recusa candidatos por repeticao e escolhe outro, o motivo
aparece no relatorio mesmo com o slot preenchido:

```
---- 15:00  [contraponto tecnico (anti-hype)] ----
nota: 2 candidato(s) recusado(s) antes deste (assunto 'ia' em cooldown)
```

## Post de noticia exige conteudo, nao manchete

Um item de agregador traz o titulo e a linha de placar ("212 pontos na front
page"). Escrever a partir disso produz um post que apenas repete a manchete e
admite que nao conseguiu verificar nada — o autor rejeitou exatamente isso em
2026-10-13. Duas defesas:

1. **No pool** (`planResearchCandidates`): so vira candidato de noticia o item
   cujo `extent` seja `resumo` — algo que a FONTE publicou sobre o item. Item
   so com manchete/metadados e descartado, e o motivo do SKIP diz isso. O
   cliente do Hacker News passou a usar o corpo do texto (`story_text`) quando
   existe, em vez de so o placar.
2. **No rascunho** (`validateFactual`): se o texto ADMITE que nao tem nada alem
   da manchete ("o titulo ja diz tudo", "sem o texto integral nao da para
   dizer"), o post e recusado — e a manchete traduzida que a especificacao
   proibe.

Consequencia honesta: o slot das 12:00 pode ficar **vazio** em dias em que as
fontes so trazem manchetes. Isso e o comportamento correto — melhor um horario
sem post do que um post que nao diz nada.

## Geracao antecipada (texto pronto antes da hora)

O texto e **gerado `publisher.prep.lead.min` minutos ANTES** do horario (default
10) e **publicado na hora exata**. Sem isto, gerar no proprio horario significa
que qualquer lentidao de rede ou rejeicao do gate faz o post perder a hora;
gerando antes, o texto ja esta validado e esperando quando o relogio chega.

Fluxo de um horario (ex.: 12:00, com lead de 10 min):

1. **11:50** — o daemon roda o pipeline (pesquisa, selecao, geracao, gates) e
   salva o texto como `scheduled` para 12:00.
2. **12:00** — um passe separado do daemon (`publishDueScheduled`, roda a cada
   ciclo) publica o que ja estava agendado e venceu.

Se a geracao **falhar na janela** (sem material, ou gate factual barrou), o
daemon tenta de novo em `publisher.prep.retry.min` minutos (default 3, curto de
proposito) — e nao nos 20 da retentativa normal — para ainda pegar a hora. A
retentativa respeita o horario: nunca agenda uma tentativa depois do horario
alvo (na janela) nem depois do proximo slot (fora da janela).

O adiantamento vale **so para a ocorrencia do relogio** (a que tem `HH:MM` igual
ao `clock` da agenda). Uma **retentativa** cai a poucos minutos de distancia — ou
seja, dentro da janela de 10 min — e seria disparada no mesmo instante em que foi
agendada, queimando o orcamento de retentativa em segundos e deixando o horario
vazio. Retentativa roda na hora dela. (Bug real, pego pelo teste de retentativa
em 2026-10-14; o codigo agora decide por `isClockRun`.)

| chave | env | o que faz |
|---|---|---|
| `publisher.prep.lead.min` | `KOF_PUBLISHER_PREP_LEAD_MIN` | minutos de antecedencia da geracao (10; 0 desliga) |
| `publisher.prep.retry.min` | `KOF_PUBLISHER_PREP_RETRY_MIN` | minutos ate a nova tentativa dentro da janela (3) |

Em modo `assisted` nada disto muda: o rascunho continua indo para REVIEW.

## Retentativa do horario (nao perder o post do dia)

Se um horario **nao consegue postar** — a pesquisa nao achou candidato, ou o
gate factual barrou o rascunho — o daemon **tenta de novo mais tarde no mesmo
dia**, em vez de esperar 24h. A nova tentativa refaz o pipeline inteiro
(pesquisa nova, selecao nova), porque a causa costuma ser "nao ha material
agora" e o material muda ao longo do dia.

Regras (todas configuraveis, defaults entre parenteses):

| chave | env | o que faz |
|---|---|---|
| `publisher.retry.max` | `KOF_PUBLISHER_RETRY_MAX` | maximo de ocorrencias daquele horario por dia (3) |
| `publisher.retry.delay.min` | `KOF_PUBLISHER_RETRY_DELAY_MIN` | minutos ate a nova tentativa (20) |

A retentativa **nunca passa por cima do proximo horario**: se nao couber antes
dele, e descartada (o proximo horario roda de qualquer forma). E **nunca inventa
conteudo**: uma retentativa que tambem nao acha material honesto continua
pulando, dentro do orcamento. Em modo `assisted` o `REVIEW` e o resultado
esperado, entao nao conta como falha; em `autonomous`, um rascunho retido conta
como falha e entra na retentativa.

## Subir o servico (start reproduzivel)

O daemon herda o ambiente de quem o inicia, e nem os segredos nem os ajustes de
retry vivem em arquivo de configuracao — um `publisher start` a mao sobe sem
token. Use o script:

```bash
tools/kof-publisher-service.sh start|stop|status|logs
```

Ele faz o `source` dos segredos (`kof-lm.env`, `linkedin-secrets.env`,
`github-secrets.env`), liga o opt-in de perfil pessoal **so no ambiente do
processo**, e define a janela de retry maior. Nada de credencial vai para o
perfil, para o banco ou para o log.

## Repeticao: comparar o SUJEITO, nunca um template

O gate de repeticao compara o **sujeito** do candidato, e cada origem tem uma
forma propria — usar a errada foi a causa de dois slots vazios no mesmo dia:

| origem | o que e comparado | por que |
|---|---|---|
| `repo` | **identidade** (o nome do repositorio) | o tema e um template ("atualizacao no projeto X") que todo repo compartilha |
| `profile` | **so o `theme`** | o `argument` repete o texto ou e um boilerplate comum a toda a lista |
| `research` | `theme` + `argument` | titulo e resumo sao conteudo real, sem boilerplate |

Medido em 2026-10-12: comparar o template dos repos fez dois repos **diferentes**
marcarem 88% e recusou os 16 (slot das 06:00 vazio); comparar o boilerplate dos
`rejects` fez onze itens **nao relacionados** marcarem 47-53% e recusou os 11
(slot das 18:00 vazio). Os dois casos tem teste de regressao.

## Janela de retry da publicacao

O padrao do codigo e 3 tentativas com 2s de espera (~6s no total) — curto demais
para uma oscilacao real de rede: medido em 2026-10-12, uma falha transitoria
queimou as 3 tentativas em 6 segundos e marcou o post do dia como `failed`. Em
producao o daemon sobe com uma janela maior, por env (o config do Kof resolve
`publisher.attempts` como `KOF_PUBLISHER_ATTEMPTS`):

```bash
export KOF_PUBLISHER_ATTEMPTS=5
export KOF_PUBLISHER_ATTEMPT_DELAY_MS=10000   # 10s, dobrando: ~2min30 no total
```

O default do codigo fica curto de proposito: os testes de recusa de credencial
precisam terminar rapido.

## Assinatura do Kof (grito de guerra + link)

Kof e a linguagem da autora e o projeto principal dela. **Todo** post que fale
do Kof (a linguagem, Kof4j, KofOS, o ecossistema) recebe automaticamente, no
fim:

```
https://koflang.github.io

KOFFIE VOOR IEDEREEN
```

O grito de guerra e sempre a **ultima linha**. Isso e garantido por codigo
(`ensureKofSignature`), nao apenas pedido no prompt — o modelo esquece, e uma
assinatura obrigatoria nao deveria depender de revisao manual. A deteccao e por
token inteiro: `kofbank` **nao** herda a assinatura (e um projeto COBOL). O link
da assinatura tambem e excluido da checagem de rastreabilidade (ele nao e uma
fonte consultada). O slot das **06:00** tambem pode escolher uma noticia ou
curiosidade sobre o Kof, nao so uma mudanca de commit.

## Link do repositorio nas postagens

Todo post de **atualizacao de repositorio** termina com o link do proprio
repositorio, logo acima da assinatura do Kof quando ela existe:

```
A mudanca que chegou ao enois-backend ...

https://github.com/Rede-ENois/enois-backend
```

Como a assinatura, o link e **conteudo fixo aplicado por codigo**
(`storedWithRepoLink`), nao um pedido ao modelo: o link e sempre a penultima
linha (ultima antes do grito de guerra) e o texto entregue ao prompt e ao
Gate de repeticao esse trecho fixo e retirado do texto. A URL do repo entra como **fonte da
pauta** (`SourceRef` com `source_type=repo`), entao a checagem de
rastreabilidade nao acusa o link como uma citacao sem fonte.

Detalhe que surgiu do proprio gate: como o link e igual em dois posts sobre o
MESMO repositorio, comparar o texto como armazenado fazia o segundo post
parecer repeticao do primeiro. Por isso `plan` (e o daemon) comparam a
**prosa antes do link** (`recentProseExcluding`). Um rascunho com ressalva
factual guardado em REVIEW tambem carregava o link e bloqueava o repositorio
para o proximo plano: esse rascunho e retirado do REVIEW (vai para
`cancelled`, texto preservado) com a ressalva no campo de erro, e a analise do
repositorio continua na base.

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
