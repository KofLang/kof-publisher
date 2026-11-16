# Personalidade editorial — decisões

Este documento registra **por que** o perfil de personalidade tem a forma que
tem e **o que** o código faz com ele. Fonte de verdade da autora: o próprio
`examples/mel.kofmd` (KofMD). Nada de personalidade vive fora dele.

---

## 1. Por que os posts saíam genéricos (investigação, 2026-11-07)

O perfil já era rico em conteúdo. O problema estava em **onde** esse conteúdo
era usado, e em duas instruções de código que o contradiziam:

| # | Sintoma | Causa medida no código |
|---|---------|------------------------|
| 1 | Voz "de agente editorial de uma empresa" | `Editorial.systemRules()` abria o *system prompt* com "Voce e o agente editorial de uma empresa" |
| 2 | Tamanho e hashtag divergentes do perfil | o mesmo `systemRules()` mandava "Maximo 1300 caracteres. Sem hashtag." enquanto o perfil declara `max_chars: 3000` |
| 3 | Personalidade só como "regra" solta | `voiceRules()` anexava até 28 itens de `voice.guide` como `REGRA DA AUTORA`, num bloco entremeado por regras mecânicas do validador |
| 4 | Nenhuma emoção | não existia nenhum conceito de estado emocional nem de intensidade em todo o código |
| 5 | Post sem motivo de existir | o objetivo de cada horário era uma frase por função (`planObjectiveFor`); nada perguntava "por que este post existe hoje" |
| 6 | Identidade só depois do payload | `contextBrief()` (empresa, público, tópicos) vinha antes de tudo no *user prompt*; identidade e psique não entravam |
| 7 | Revisão descrita em tom áspero | `reviseIn()` mandava "CORRIJA estes problemas e reescreva", sem nenhuma cláusula de preservação da voz |
| 8 | Repetição só lexical | memória de abertura/fechamento + n-gramas; a assinatura de tese (`Thesis.kf`) existia, mas só no planejamento, não na validação |

O perfil em si não era o problema. A forma de consumi-lo era.

## 2. Decisões

### 2.1 A personalidade vive no KofMD, em seções com nome

Segue o padrão que `Context.kf` já usa: cada `# <seção>` vira um escopo e as
chaves são lidas por `sectionField` / `sectionList`. Nenhuma chave mudou de
lugar nem de significado; apenas foram **adicionadas** seções:

| Seção | Papel | Status |
|-------|-------|--------|
| `# company` | identidade central (nome, descrição, posicionamento) | existente |
| `# background` | trajetória, o que a experiência permite ver | novo |
| `# values` | convicções que dão base às emoções | novo |
| `# personality` | traços que coexistem (inclui as contradições) | novo |
| `# emotional_profile` | estados emocionais e quando cada um nasce | novo |
| `# language` | voz: cadência, expressões possíveis, clichês proibidos | novo |
| `# strong_language` | quando usar linguagem forte (e quando não) | novo |
| `# technical_domains` | domínios e relação com cada um | novo |
| `# opinions` | posições registradas | existente |
| `# editorial_engine` | como um post ganha motivo de existir | novo |
| `# diversity` | variedade editorial | novo (migrado de `editorial.diversity`) |
| `# platforms` | adaptação por plataforma | novo |
| `# factuality` | o que nunca pode ser inventado e a escala de evidência | novo (migrado de `editorial.authenticity` + `# evidence`) |
| `# review` | perguntas da revisão editorial | novo |
| `# restrictions` | limites duros | novo (migrado de `# avoid`) |

`thinking`, `argumentation`, `rejects`, `evidence`, `facts`, `principles`,
`topics`, `goals`, `voice`, `editorial`, `category`, `schedule` continuam
exatamente onde estavam.

### 2.2 Migração explícita, sem duplicação

`loadCompany` resolve cada seção nova com **fallback explícito**: se `# diversity`
não existir, usa `editorial.diversity`; se `# factuality` não existir, usa
`editorial.authenticity`; etc. Um perfil antigo continua funcionando igual.

Para o perfil atual, o conteúdo foi **movido** (não copiado) para as seções
novas e `examples/mel.kofmd.legacy` guarda a versão anterior, para o antes/depois.

O comando `publisher check` passa a imprimir, seção por seção, **se ela veio do
perfil ou se o parser caiu no fallback** — nada de default silencioso.

### 2.3 Quais chaves são obrigatórias

Regra: o que muda o que é escrito é obrigatório para um perfil **autoral**
(o que declara `# personality`); o que é só organização aceita ausência.

Obrigatórias quando existe `# personality`:

- `emotional_profile.levels` — os seis níveis (0-5). Faltar um é erro de
  configuração, não default.
- `emotional_profile.states` — `estado: nivel, gatilho` para cada emoção.
- `editorial_engine.questions` — as perguntas do motivo de existir.
- `diversity.formats` — os formatos válidos.
- `review.checks` — as perguntas da revisão.
- `strong_language.levels` — a partir de qual nível a linguagem forte é legível
  (inteiro; ausência = erro).

Erros de configuração são **lançados** (`throw`) com o nome da seção e da
chave: `loadCompany` nunca devolve um valor vazio que esconda um problema.

### 2.4 O que o código faz com isso (pipeline)

```
identidade no SYSTEM prompt (persona = autora, montada do KofMD)
   -> (user prompt) perguntas do motor editorial + o que a pauta NAO pode ser
   -> (user prompt) DIRETIVA: dominio, nivel, emocao, formato  [calculada sem IA]
   -> material/research/GitHub (como antes)
   -> geracao (1 chamada)
   -> validacao mecanica (tamanho, travessao, CTA, cliches, muletas, repeticao)
   -> revisao (1 chamada, proibida de neutralizar) -> validacao de novo
   -> barreira de fidelidade factual (inalterada)
```

**Identidade no system prompt.** `identityRules()` (em `Editorial.kf`) monta,
nessa ordem: quem escreve → o que valoriza → como é (incluindo as
contradições) → a escala 0-5 → o que levanta cada estado → regras da emoção →
domínios e ângulo → posições sobre a indústria → sobre ensino/comunidade →
projetos → fala (expressões, ritmo, o que não é) → as regras de escrita que
ela mesma declarou → linguagem forte → estruturas que nunca usa → restrições →
onde escreve → o que não inventa → checks de revisão → "na revisão você não
pode neutralizar a sua voz". A primeira frase é literalmente: *"Voce ESCREVE
COMO Mel Santos, e o texto abaixo e a sua propria vida e a sua propria cabeca,
nao um personagem que voce interpreta."* Um perfil antigo (sem `# personality`)
continua recebendo o prompt genérico de antes — nada de perfil antigo ganha
identidade inventada.

**Regras mecânicas por último, vindas do perfil.** `voiceRulesFor()` anexa ao
final, e só o que o perfil declara (tamanho de `max_chars`, travessão, CTA,
coach, hashtag, menção a IA). O "Maximo 1300 caracteres. Sem hashtag."
hardcoded sumiu.

**Diretiva calculada sem IA (`editorialFrameOf` + `directiveOf`).**

1. *Domínio*: o assunto é casado com `# technical_domains` (nome do domínio →
   2; ≥2 palavras do ângulo com ≥5 letras → 1). O melhor casamento dá o nível-base.
2. *Estado emocional*: se algum gatilho de `# emotional_profile.states` aparece
   no assunto, esse estado é usado e o nível sobe para o nível declarado dele.
3. *Piso do horário*: se nenhum gatilho disparou, o estado-base do horário
   (projetos→satisfação, notícias→curiosidade, contraponto→irritação,
   observação→humor) é o **piso** — se o perfil declara esse estado com base 3,
   um contraponto não sai nível 0. Um gatilho acima do piso ainda ganha.
4. *Formato*: entre os formatos que o perfil associa à função do horário,
   escolhe um por hash determinístico do assunto — a mesma pauta dá o mesmo
   formato, e os horários do dia não repetem.
5. *Linguagem forte*: permitida só se `nivel >= strong_language.levels`.

Tudo isso é impresso no `plan`, no `samples` e no log (`DIRETIVA: dominio=…
base=… emocao=… nivel=… formato=… funcao=…`), para conferir **por que** um
post saiu irritado ou calmo.

**Motor editorial.** Antes de escrever, o prompt carrega as
`editorial_engine.questions` ("se a pauta não responde às duas primeiras, não
escreva") e as `engineAvoidForms`. Se a resposta começar com `SKIP:`, o
Publisher trata como pauta recusada, não como rascunho. Além disso,
`reasonToExist()` recusa pauta vazia ou composta **só** de conectivos — recusa
por falta de assunto, não por tamanho: "sistemas legados" e "JVM" são pautas
válidas.

**Revisão preserva.** `reviseFrame()` recalcula a diretiva e diz: *"Corrija
apenas o que os problemas abaixo apontam. Mantenha a voz, a intensidade
emocional e o ponto de vista: a correção não pode amaciar o texto, não pode
virar texto neutro de manual e não pode trocar a sua opinião por uma versão
equilibrada que não diz nada."*

**Novas checagens do validador** (determinísticas, não "voto de modelo"):

| Checagem | Resultado |
|----------|-----------|
| estrutura clichê declarada em `language.cliche_structures` (`nao e sobre X, e sobre Y`) | **problema** |
| mais de uma frase-assinatura no mesmo texto | aviso |
| mesma frase-assinatura em publicação recente | aviso |
| muleta de influenciador (`recentemente`, `tenho pensado`, `fiquei pensando`…) | aviso; **problema** se já apareceu no histórico |

As muletas ficam **no código**, não no perfil: são propriedade do gênero
LinkedIn, não desta autora. O perfil guarda apenas as expressões reais dela em
`signature_phrases` (que antes continha justamente as muletas).

**Comando `samples`.** `publisher samples --scenarios examples/amostras.kofmd
--runs N` roda os 25 cenários N vezes contra uma LM, **sem gravar rascunho e
sem publicar nada**, e imprime por amostra: diretiva, validação e texto.
É a ferramenta de inspeção exigida pela missão.


### 2.5 Limites honestos

- A revisão interna é um LLM se lendo com instrução: **reduz** o
  esvaziamento, não o impossibilita. A medição disso está em `tests/Personality.kf`
  com contador de vazamentos.
- A "relação com a autora" é casamento de termos declarados, não compreensão.
  Um assunto fora dos domínios cai em nível 0-1, que é o comportamento
  pretendido (ver cenário 20/21 dos testes).
- O teste de personalidade usa um fixture que **respeita** o contrato do
  prompt (responde ao bloco `DIRETIVA EDITORIAL`). Ele prova que o Publisher
  formula e transporta a diretiva; não prova que um modelo real obedece.
  Amostras com o modelo real estão em `docs/amostras/`.

## 3. Escala de intensidade

| Nível | Estado | O que muda no texto | Como o código chega nele |
|-------|--------|---------------------|--------------------------|
| 0 | neutro | técnico, informativo, sem emoção forçada | domínio desconhecido e horário explicativo |
| 1 | interesse | curiosidade, envolvimento moderado | domínio conhecido sem gatilho emocional |
| 2 | entusiasmo | escrita mais solta e expressiva | gatilho de satisfação/admiração no domínio |
| 3 | convicção | opinião forte, argumento direto | horário de contraponto ou opinião registrada casada |
| 4 | indignação/euforia | ironia, sarcasmo, linguagem intensa | gatilho de indignação/frustração e formato de crítica |
| 5 | intensidade máxima | só quando o contexto justifica de verdade | gatilho de conquista extraordinária ou de protesto declarado |

Nível 5 é alcançável, nunca padrão: exige gatilho emocional **e** formato de
missão/protesto no perfil.

## 4. Testes de comportamento (`tests/Personality.kf`)

12 testes, contra a CLI real e uma LM-fixura que **respeita o contrato** do
prompt (lê `intensidade:` da diretiva e escreve naquele nível):

1. o perfil carrega com proveniência, 4 horários e os estados declarados;
2. perfil autoral sem `emotional_profile.states` é **recusado**;
3. estado sem nível é **recusado**;
4. o system prompt fala **como a autora** (e não contém mais "agente editorial
   de uma empresa" nem "Maximo 1300 caracteres");
5. a diretiva é derivada do perfil: java→jvm base 2; "palavrao"→indignação 4;
   "inteligencia artificial"→irritação 3; neutro→0; e o formato aparece;
6. o nível muda a resposta;
7. `--runs 4` não repete abertura e usa ≥4 formatos distintos;
8. pauta sem assunto → `SKIP: pauta sem assunto`;
9. estrutura clichê → problema de validação;
10. muleta de influenciador → aviso;
11. a revisão mantém a voz (`nao pode amaciar o texto`);
12. perfil antigo → `personalidade: perfil autoral declarado = nao` e
    `emotional_profile=fallback:sem # personality`.

O cenário de 25 pautas está em `examples/amostras.kofmd`, e as amostras reais
(antes/depois) em `docs/amostras/`.

## 4.0 Um pouco dela em todo post: os motivos de assinatura

Um post em nível 0 é tecnicamente correto e **anônimo**: poderia ter sido
escrito por qualquer pessoa que leu o mesmo artigo. A personalidade estava no
prompt, mas não necessariamente no texto.

`# signature motifs` resolve isso. O perfil declara os ângulos que ela traz a
**qualquer** assunto (custo de manutenção antes da novidade; separar o que está
documentado do que foi verificado; sistema financeiro como lente; autonomia
técnica; o que o time sustenta acima do desenho bonito; quem aprende não paga a
conta de quem vende atalho; máquina antiga e Linux; leitura de ecossistema de
Java; precisão acima de tom; desconfiança de jargão).

- **Escolha:** `pickMotif()` escolhe um por hash determinístico de
  assunto + horário, como o formato. A mesma pauta sempre carrega o mesmo
  ângulo, e horários seguidos variam.
- **Diretiva:** o motivo aparece em todo post, inclusive no nível 0, como
  *"o seu ângulo nesta publicação (o que você sempre nota, em qualquer
  assunto)"* — com a instrução de usá-lo como **critério ou observação**, não
  como frase de efeito colada no fim.
- **Validação:** se o texto não carrega nenhum motivo, sai o aviso
  *"nenhum ângulo próprio da autora no texto — o post pode ter saído genérico,
  mesmo estando correto"*; se o mesmo motivo apareceu em publicação recente,
  outro aviso pede para variar o critério, não a bandeira.
- **Nunca é invenção:** todos os motivos são posturas que ela já declara em
  `# values`, `# personality`, `# background` e `# technical_domains`. Nenhum
  acrescenta fato novo sobre a vida dela.

Um perfil sem `# signature motifs` continua funcionando e o `check` reporta
`signature.motifs=ausente` — não inventa ângulo.

## 4.1 O que a primeira rodada real ensinou (2026-11-07)

A primeira execução de `samples` com o modelo real e a barreira de fidelidade
ligada reprovou **7 de 22** amostras. O motivo não foi falta de voz: foi que o
prompt novo, ao dizer "o texto abaixo é a sua própria vida", deu ao modelo
licença para **narrar um dia de trabalho** ("passei a semana mexendo no parser",
"rodei o build"). As regras de autenticidade do perfil já proibiam isso, mas
estavam longe do material.

Correção: o prompt agora declara, logo ao lado do material, **a natureza da
pauta** (leitura, posição registrada ou notícia de terceiro, nunca um dia
vivido), com exemplos do que não pode ser narrado. Resultado: 21/22, depois
22/23 e 23/24 nas rodadas seguintes.

A mesma rodada revelou **falsos positivos** na barreira de fidelidade, que
estavam punindo as frases mais honestas do texto:

| Texto real | O que o detector fazia | Correção |
|-----------|------------------------|----------|
| "sem falar de build ou de teste que eu **não** rodei aqui" | lia "rodei" como afirmação de ter rodado | negação imediatamente antes do verbo não conta como afirmação |
| "sem mergulhar no **texto completo**" | lia como "li o texto completo" | idem, para as marcas de leitura |
| "com virtual threads **a thread** era cara" | lia como "a thread [do fórum] diz..." | só formas de relato ("a thread diz") contam |
| "a maioria **dos comentários** sobre compilador ignora isso" | lia como relato de comentários consultados | só "os comentários do artigo/da thread/do post" contam |

Regra que ficou: **um detector só é útil se distinguir a afirmação da negação
e o relato do substantivo genérico**. Cada uma dessas correções foi medida
contra o texto real que a motivou, não por intuição.

## 5. Limites honestos

- O teste com fixura prova que o Publisher **formula e transporta** a
  diretiva; não prova que um modelo real obedece a ela. Por isso os testes
  rodam N amostras, não uma, e por isso as amostras com o modelo real ficam
  versionadas para inspeção.
- A emoção é **derivada** de uma casamento de termos → gatilho declarado. Um
  assunto fora dos domínios cai no piso do horário (ou em nível 0 no horário
  explicativo), que é o comportamento pretendido, não um bug.
- A revisão feita por LLM **reduz** o esvaziamento, não o impede.
- A linguagem forte continua sujeita ao mesmo validador de conteúdo; o nível
  só a **libera**, nunca a exige.

## 6. Antes / depois (medido)

- **Antes** (`docs/amostras/antes.md`): posts reais publicados pelo código
  anterior, lidos do banco de produção em modo somente leitura. São texto
  corrido, denso, com uma tese única e nenhuma emoção declarada — "voz de
  agente editorial".
- **Depois** (`docs/amostras/depois.md`): 25 cenários de
  `examples/amostras.kofmd`, uma amostra cada, modelo real. Cada uma traz a
  diretiva (`dominio`, `nivel`, `emocao`, `formato`) e o veredito dos dois
  gates.

O que mudou de concreto, e é visível na comparação:

| Antes | Depois |
|-------|--------|
| abertura de manual ("Tem um vício de linguagem em discussão técnica que...") | abertura com posição e emoção ("Tem time que não tem problema de escala, tem problema de conversa") |
| um bloco denso de 3 parágrafos sem respiro | parágrafos curtos separados por linha em branco |
| nenhum nível emocional — tudo no mesmo tom | nível e emoção declarados e seguidos (irritação 3, satisfação 2, humor 3, curiosidade 0) |
| os mesmos conectivos corporativos | expressões da autora quando o nível permite |
| todo texto com a mesma forma | formato variado por horário e por pauta |
| não havia como saber *por que* o texto era o que era | a diretiva explica antes do texto |

O nível 0 existe e é **deliberado**: o cenário `neutro` sai técnico e direto,
sem emoção, porque a pauta não toca nenhum valor da autora. Isso é o limite
honesto do desenho, não uma falha.

## 7. Bug encontrado em produção (2026-11-07): um horário, dois posts

Na manhã de 07/11 o slot das 06:00 publicou **duas vezes** no LinkedIn: às
05:53 e às 05:56. Não foi o modelo nem o perfil — foi o agendador.

Sequência medida no log e no ledger de ocorrências:

1. 05:50 — o preparo gerou um rascunho que a barreira de fidelidade reprovou
   ("afirma em primeira pessoa que a autora fez algo"). O slot ficou em
   `review`, que em modo autônomo conta como falha, e a retentativa foi
   agendada para 05:53.
2. 05:53 — a retentativa gerou outro texto e **publicou**.
3. O laço então processou a ocorrência do relógio (06:00), que já estava
   reivindicada, e registrou `skipped / already claimed`. **Esse "skipped" foi
   contado como falha**, então uma nova retentativa foi agendada para 05:56.
4. 05:56 — como o instante ainda estava no futuro, a retentativa gerou um
   terceiro texto e **publicou de novo**.

Duas causas, ambas corrigidas:

- `already claimed` é **no-op**, não falha. Uma ocorrência já tratada não pode
  gerar retentativa.
- Um slot que **já publicou no dia** nunca é retentado
  (`Store.publishedForDay`). A retentativa existe para salvar um horário que
  não produziu nada; depois de um post bem-sucedido ela produz um segundo
  texto para a mesma hora.

Regressão coberta em `tests/Service.kf` ("a slot that already published is
never retried"), que semeia a publicação bem-sucedida, força um SKIP e exige
que **nenhuma** retentativa seja agendada.

## 8. Bug de perfil encontrado no caminho: comentário com `#` quebra a seção

O parser do KofMD trata **toda** linha que começa com `# ` como abertura de
seção, mesmo sem linha em branco antes. Os comentários explicativos que eu
tinha escrito dentro de `# memory` e `# signature` estavam, portanto,
fragmentando essas seções — `signature_phrases` e `motifs` nunca eram lidos.

Corrigido no perfil (comentários sem `#`, com a regra escrita no próprio
arquivo) e verificado por `publisher check`, que agora reporta
`signature.motifs=profile` e `memory=profile`.
