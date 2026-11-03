#!/usr/bin/env python3
"""Fake LM fixture for the PERSONAL profile pipeline (port passed in argv).

Two deterministic modes (argv[2]):
  distinct (default) -- returns a DIFFERENT clean pt-BR text per editorial
      category, so `plan` can produce four proposals that are not flagged as
      repeated (the category label arrives in the prompt as
      "CATEGORIA EDITORIAL DESTE HORARIO: <label>").
  repeat -- returns the SAME clean text every time, so the editorial memory
      (opening/closing key + n-gram overlap) must catch the second proposal
      as a re-run and discard it.

Speaks the Ollama chat protocol the Publisher uses. TEST FIXTURE ONLY: the
Kof side talks real HTTP to it, nothing in Kof is stubbed.
"""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

# A clean text per category (no em-dash, no banned opening, <= 3 hashtags,
# no colons, single dense paragraph). Each opening is deliberately distinct
# so the anti-repetition gate is not tripped between the four proposals.
BY_CATEGORY = {
    "opiniao": (
        "Pow, essa mania de enfiar IA em tudo me incomoda de um jeito honesto, "
        "porque a ferramenta resolve muito bem o que e chato de escrever mas o "
        "time que terceiriza o raciocinio paga a conta depois no codigo que "
        "ninguem entende. Eu uso IA todo dia e gosto, so nao compro o discurso "
        "de que ela substitui pensar. #ia #engenharia"
    ),
    "experiencia": (
        "Revisitar um servico de anos atras costuma mostrar que a parte que "
        "envelheceu melhor foi a decisao mais chata da epoca, a de deixar o "
        "contrato explicito em vez de otimizar cedo. A pressa de lancar "
        "esconde custo que so aparece dois anos depois, quando o time mudou e "
        "ninguem lembra porque aquilo estava daquele jeito. #java #arquitetura"
    ),
    "analise": (
        "Ontem a gente discutiu cache em camada de dados e o trade-off real nao "
        "era velocidade, era invalidação, porque acertar leitura e facil e "
        "errar escrita contamina tudo por dias sem ninguem notar. Preferi medir "
        "o hit rate antes de decidir e o numero mostrou que o gargalo estava em "
        "outro lugar, entao o cache era solucao pra problema que nao existia. "
        "#backend #performance"
    ),
    "carreira": (
        "Uma coisa que sempre me perguntam sobre virar tech lead e se vale a "
        "pena largar o codigo, e minha resposta honesta e que voce nao larga, "
        "voce troca o tipo de problema que resolve. Ensinar alguem a chegar na "
        "resposta da mais trabalho que escrever a resposta, mas e o unico jeito "
        "de o time crescer sem virar gargalo em volta de uma pessoa so. "
        "#carreira #lideranca"
    ),
}

REPEAT_TEXT = (
    "Pow, essa parada de colocar IA em tudo me incomoda de um jeito honesto, "
    "porque a ferramenta resolve bem o que e chato de escrever mas quando o "
    "time terceiriza o raciocinio a conta chega depois no codigo que ninguem "
    "entende. Uso IA todo dia e gosto, so nao compro o discurso de que ela "
    "substitui pensar. #ia #engenharia"
)

# A first-person EPISODE. The profile registers positions, never episodes, so a
# text that narrates one is inventing lived experience and the validator must
# discard it (measured on the first real run, 2026-10-11).
EPISODE_TEXT = (
    "Passei a tarde debugando um problema de concorrencia numa fila de "
    "mensagens que parecia simples e o assistente de IA me entregou uma "
    "solucao que resolvia o sintoma mas quebrava a garantia de entrega unica, "
    "entao tive que reescrever a logica de lock e validar o comportamento do "
    "consumer na mao, gastando mais tempo corrigindo do que teria gasto "
    "escrevendo do zero com clareza mental. A licao e que a ferramenta acelera "
    "a digitacao mas nao substitui o raciocinio sobre o contrato do sistema. "
    "#java #arquitetura"
)

# A claim to have READ the source. The publisher only ever holds the item's
# title, url, dates and the source's own blurb, so the claim is unfounded by
# construction and must be discarded.
READCLAIM_TEXT = (
    "O ponto que o artigo levanta sobre complexidade acidental e correto e vale "
    "estender, porque a mesma logica aparece em sistemas financeiros onde a "
    "abstracao esconde o custo real do acesso ao disco. Parei pra ler o artigo "
    "inteiro e o argumento se sustenta melhor na segunda metade, quando entra "
    "no caso concreto de um pipeline que trocou a ferramenta madura por uma "
    "mais nova sem medir o ganho, e o resultado foi latencia pior com mais "
    "codigo para manter. Nao e uma defesa do imobilismo, e um pedido de "
    "evidencia antes da adocao. #arquitetura #engenharia"
)

# A first-person episode wearing a retrospective verb ("me fez parar e
# reler..."). Same invention as EPISODE_TEXT, different wording — measured on
# the real run of 2026-10-11 on the projects slot, where it slipped past the
# phrase list until "me fez <retrospectiva>" was added.
RETRO_EPISODE_TEXT = (
    "O projeto ganhou um fix que me fez parar e reler a documentacao inteira do "
    "runtime antes de entender o que tinha mudado, porque o problema estava "
    "escondido num detalhe de arredondamento que so aparece quando o volume de "
    "operacoes cresce e a divergencia de centavos vira relatorio contabil "
    "errado no fechamento do dia. A correcao trocou a operacao simples por uma "
    "que arredonda explicitamente, o que parece cosmetico mas e o tipo de "
    "detalhe que separa um sistema auditavel de um passivo escondido. "
    "#engenharia"
)

# A news post that asserts a PROPERTY of the tool the material never states.
# The consulted blurb is "88 pontos na front page"; nothing says where the
# program runs. Measured on the real run of 2026-10-11, where the generator
# wrote that the tool "roda no dispositivo, sem enviar audio para servidores
# externos" and made that architecture the reason the news mattered.
LOCALCLAIM_TEXT = (
    "A ideia de um transcritor de voz que roda no dispositivo e processa tudo "
    "localmente resolve um problema que ninguem quer admitir em voz alta, que e "
    "a dependencia de servico externo para uma tarefa que deveria ser privada "
    "por padrao. Sem enviar audio para fora da maquina, a ferramenta muda a "
    "conversa sobre custo e sobre confianca, porque o dado sensivel nunca sai "
    "do seu controle. O ganho nao esta em transcrever melhor que os modelos "
    "grandes, esta em nao precisar de rede nem de conta paga para escrever um "
    "comentario longo de codigo ou uma especificacao tecnica. #ferramentas"
)

# A news post that asserts an ABSENCE the material never states. The consulted
# item says only "never needs the internet"; the camera and the app are the
# generator's invention, negated. Measured verbatim from
# pub-12-00-noon-22f8ee51 (real run of 2026-10-11). The property list is
# positive-only ("usa a camera"), so a denial slipped past it.
ABSENCE_CLAIM_TEXT = (
    "Sobre o color picker, a ideia e simples e resolve um problema real de "
    "design: pegar uma cor do mundo fisico sem depender de camera, app "
    "instalado ou conexao. O que me chama atencao aqui nao e a tecnologia em "
    "si, mas a decisao de restringir o escopo. Em vez de tentar ser um canivete "
    "suico digital, ela abraca uma limitacao fisica como recurso. Isso e "
    "engenharia honesta: voce define o contexto de uso e elimina tudo que nao "
    "serve para ele. #ferramentas"
)

# A projects post that asserts a verification RESULT nobody produced. The
# repository analysis records verified_build=false and "nada foi executado
# aqui"; the post calls "a prova de que o codigo compila" what is only the
# existence of source files. Measured from pub-06-00-morning-de2a104a (real
# run of 2026-10-11). Distinct from TESTCLAIM_TEXT, which claims the tests
# GUARANTEE something; this one claims the build HAPPENED.
UNVERIFIED_CLAIM_TEXT = (
    "O projeto avancou no nucleo e a mudanca real nos commits recentes esta na "
    "correcao da matematica financeira, com o calculo de juros compostos "
    "ajustado para evitar truncamento decimal. A estrutura separa as "
    "responsabilidades entre foundation, customers, accounts e ledger, seguindo "
    "o padrao de double-entry que define o comportamento contabil do sistema. "
    "O codigo compila e segue a arquitetura proposta, com os arquivos de teste "
    "presentes na raiz do repositorio. A decisao de manter a logica de negocio "
    "dentro do COBOL, sem vazamentos para camadas externas, e um trade-off "
    "tecnico explicito. #engenharia"
)

# A PROJECTS post that opens by narrating an encounter with the repository
# ("Peguei o X de volta pra mao", "a primeira coisa que me chamou atencao").
# The publisher read a commit log; it did not pick anything up or notice
# anything with its eyes. Measured from the real run of 2026-10-11.
ENCOUNTER_TEXT = (
    "Peguei o projeto de volta pra mao depois de um tempo e a primeira coisa "
    "que me chamou atencao nao foi o codigo em si, mas o esqueleto da "
    "configuracao. A estrutura base e solida, com separacao correta entre app, "
    "spec e tsconfig, mas o README ainda entrega o texto padrao do gerador, "
    "cheio de instrucoes genericas sobre como subir o servidor local. Ter "
    "arquivos de teste na raiz e bom sinal de intencao, mas nao prova cobertura "
    "real nem qualidade, porque a analise so leu a estrutura e nao compilou "
    "nada. Ter a configuracao correta e ter testes escritos sao coisas "
    "diferentes de ter um sistema que se comporta como esperado. #engenharia"
)

# A NEWS post that asserts third-party REACTION to the item. The material is a
# title, a url, a date and a point count; it has no comment section and no
# reader response. Measured from the real run of 2026-10-11, where the news
# post described "a reacao de quem leu isso como se fosse uma tragedia".
REACTION_CLAIM_TEXT = (
    "Achei um post de blog com um titulo que soa como despedida, e o que mais "
    "me chamou atencao nao foi o texto, mas a reacao de quem leu isso como se "
    "fosse uma tragedia ou um fim de carreira. A gente criou uma expectativa "
    "estranha de que quem e relevante tecnicamente precisa estar produzindo "
    "conteudo publico o tempo todo, senao desapareceu do mapa. Essa narrativa "
    "de sumico confunde visibilidade com competencia e transforma a atividade "
    "editorial num indicador de saude profissional. Talvez a gente deva parar "
    "de medir relevancia pela frequencia de publicacao. #engenharia"
)

# A NEWS post that narrates the author's own day around the item. The pauta
# holds a consulted item, not a working day. Measured on the real run of
# 2026-10-11, where the news slot opened with "Passei o dia com a cabeca
# dividida entre um build de sistema financeiro e um link que apareceu no
# Hacker News" — the episode check was scoped to profile/repo at the time.
NEWS_EPISODE_TEXT = (
    "Passei o dia com a cabeca dividida entre um build de sistema financeiro e "
    "um link que apareceu no agregador, e o contraste me fez pensar em como "
    "tratamos o ambiente como algo passivo. No meu trabalho com transferencias "
    "e cobranca, vejo diariamente logica que existe mais para proteger um "
    "processo quebrado do que para garantir a integridade do dado, e a "
    "ferramenta comentada levanta a mesma pergunta sobre atrito desnecessario. "
    "A ideia vale a pena pelo que ela obriga a discutir, nao pelo anuncio. "
    "#engenharia"
)

# A post that claims the author DID the work ("Fiz um merge", "Ajustei...") on
# a pauta whose material is a read-only repository analysis. Measured on the
# real run of 2026-10-11: the projects post opened with "Fiz um merge no
# kofbank que corrigia o calculo de juros compostos" and "Ajustei para usar
# COMPUTE ROUNDED".
ACTIONCLAIM_TEXT = (
    "Fiz um merge no projeto que corrigia o calculo de juros compostos e o "
    "problema nao era a formula, era como a linguagem lidava com a precisao "
    "decimal em operacoes encadeadas. Ajustei para usar arredondamento "
    "explicito na rotina de composicao, garantindo que o truncamento silencioso "
    "nao acumulasse erro ao longo do tempo. A estrutura do repositorio separa "
    "fundacao de logica de dominio e os commits recentes mostram essa "
    "disciplina, com correcoes pontuais seguidas de documentacao de evidencia. "
    "#engenharia"
)

# A projects post that upgrades "there are test files" into "the tests
# guarantee X". The repository analysis records only that test files exist and
# that nothing was executed, so the claim is unsupported. Measured on the real
# run of 2026-10-11.
TESTCLAIM_TEXT = (
    "O projeto avancou no nucleo e o commit mais recente corrige a matematica "
    "de juros compostos, trocando a operacao simples por arredondamento "
    "explicito. Isso significa que os testes presentes no repositorio validam "
    "invariantes de dupla entrada e idempotencia nas operacoes basicas, o que "
    "da confianca para seguir com a proxima camada de integracao sem refazer a "
    "base contabil. A separacao entre fundacao e dominio ajuda a isolar onde o "
    "dinheiro e calculado de onde ele e registrado. #engenharia"
)

# The same unsupported upgrade, but with the denial and the guarantee in the
# SAME sentence, which is how the real draft of 2026-10-11 actually read. A
# sentence-level check sees "nao cobrem" and skips the whole thing, so the
# guarantee in the first clause survives. Copied from pub-06-00-morning-8948d1a7.
TESTCLAIM_DENIAL_TEXT = (
    "O projeto avancou no nucleo e o commit mais recente corrige a matematica "
    "de juros compostos, trocando a operacao simples por arredondamento "
    "explicito. Isso significa que os testes presentes no repositorio validam "
    "invariantes de dupla entrada e idempotencia nas operacoes basicas, mas "
    "nao cobrem todo o fluxo de pagamento nem a reconciliacao complexa que o "
    "README descreve como alvo futuro. A separacao entre fundacao e dominio "
    "ajuda a isolar onde o dinheiro e calculado de onde ele e registrado. "
    "#engenharia"
)

# The same test-guarantee upgrade in its infinitive/concessive form. The
# denial sits after "embora" (not "mas") and the guarantee verb is "garantir"
# (not "garantem"), so both the clause split and the verb list missed it.
# Measured verbatim from pub-06-00-morning-4779c475 (real run of 2026-10-11).
TESTCLAIM_EMBORA_TEXT = (
    "O log de commits do projeto mostra um ajuste fino na logica de juros "
    "compostos, com arredondamento explicito para evitar truncamento decimal. "
    "A estrutura mantem o nucleo isolado, com camadas de fundacao para lock "
    "atomico, journaling e idempotencia, tudo documentado como requisito. Os "
    "testes existem como golden datasets e verificacoes de invariantes, o que e "
    "suficiente para garantir que as regras contabeis nao se percam durante "
    "refatoracoes, embora nao substituam a validacao de comportamento real. E "
    "engenharia aplicada, sem hype. #engenharia"
)

# B: hardware/energy/precision claims about a product the blurb only NAMED.
# The consulted summary says "a Aurora lancou um sensor de temperatura"; the
# post adds battery life and a bit depth nobody published.
HARDWARE_CLAIM_TEXT = (
    "A Aurora lancou um sensor de temperatura domestico e o que me chama "
    "atencao e a proposta de usar pouca bateria mantendo leitura precisa, "
    "porque sensores baratos costumam trocar autonomia por exatidao. Se a "
    "leitura realmente se mantem estavel sem recalibracao frequente, o ganho "
    "nao esta no hardware em si, esta em nao precisar de manutencao constante "
    "num dispositivo que fica esquecido num canto da casa. #hardware"
)

# A post written in PARAGRAPHS, separated by blank lines. The profile asks for
# "poucos paragrafos grandes, 3 a 6 no post todo" and LinkedIn renders a blank
# line as a paragraph break, so the publisher must NOT flatten these into one
# dense block (it did: cleanDraft called strings.normalizeWhitespace, which
# collapses newlines too).
PARAGRAPH_TEXT = (
    "Uso IA todo dia para o trabalho mecanico e isso me economiza tempo de "
    "verdade, porque boilerplate nao precisa de atencao humana para nascer.\n\n"
    "O que me incomoda nao e a ferramenta, e o discurso em volta dela, que "
    "trata resposta probabilistica como se fosse garantia e transforma "
    "aceitar sugestao em decidir arquitetura.\n\n"
    "Meu criterio e simples, se o problema tem solucao deterministica eu "
    "escrevo o codigo e sigo o dia, e a IA entra onde o espaco do problema e "
    "aberto demais para regra fixa, sempre comigo conferindo o resultado."
)

# A draft where a phrase of the episode list ends one sentence and "eu" starts
# the next: "ser viavel no dia a dia. Eu comecei com Java em 2009". It must NOT
# be read as an episode (the mark "no dia a dia eu" only counts inside one
# sentence). Measured from the real 12:00 draft of 2026-10-12.
EPISODE_BOUNDARY_TEXT = (
    "Essa pergunta sobre celular Linux virar alternativa real voltou a "
    "circular essa semana e ela e boa porque nao e sobre gostar de Linux, e "
    "sobre o que faz um telefone ser viavel no dia a dia. Eu comecei com Java "
    "em 2009 no contexto de Symbian, entao vi de perto um sistema capaz que "
    "foi engolido por ecossistema, driver e acordo com operadora."
)

# A post ABOUT Kof that the model wrote WITHOUT the mandatory signature. The
# publisher must add the link and put the battle cry last (author-mandated, so
# guaranteed deterministically rather than hoped for in the prompt).
KOF_NO_SIGNATURE_TEXT = (
    "O Kof 0.5.0-beta compila para JVM e o que me interessa nele nao e a "
    "sintaxe bonita, e o fato de a linguagem tratar o alvo como contrato "
    "explicito, entao o mesmo fonte tem chance de virar bytecode sem que eu "
    "precise reescrever a regra de negocio para cada runtime."
)

# A post about kofbank (a COBOL project) that must NOT inherit the Kof battle
# cry: the signature is about Kof, not about every repo whose name starts with
# "kof".
KOFBANK_NO_SIGNATURE_TEXT = (
    "O kofbank corrigiu o calculo de juros compostos trocando a operacao "
    "simples por arredondamento explicito, e o que me interessa ali nao e a "
    "correcao em si, e a decisao de manter a regra contabil dentro do COBOL em "
    "vez de espalhar a conta por uma camada moderna."
)

# A projects post that mentions "compilador" (the noun) and never claims the
# build ran. The assertion "compila" matched INSIDE "compilador" and held this
# kind of post back (measured 2026-10-13, a careful Kof4j post).
COMPILER_NOUN_TEXT = (
    "O log do Kof4j mostra uma correcao pequena e chata, a remocao de uma "
    "definicao duplicada que tinha sido anexada em vez de substituir a "
    "anterior, e isso diz mais sobre disciplina de compilador do que qualquer "
    "anuncio de recurso novo. O que esta documentado no changelog e encontrado "
    "no codigo nao e o mesmo que verificado rodando, e o repositorio tem pasta "
    "de teste cujo nome nao prova cobertura. O comportamento observavel e o "
    "que da para afirmar."
)

# A news post that restates the headline and ADMITS it could not go further.
# This is what the author rejected on 2026-10-13: "o titulo ja diz tudo que da
# para afirmar com seguranca". A translated headline is not a news post.
HEADLINE_ONLY_TEXT = (
    "Apareceu hoje esse texto com um titulo sobre uma alegacao de matematica, e "
    "o titulo ja diz tudo que da para afirmar com seguranca, que existe a "
    "alegacao e que alguem olhou a conta. Sem o texto integral nao da para "
    "dizer se a prova fecha ou se o ganho se sustenta fora do benchmark "
    "escolhido. O que da para dizer e o criterio, mostrar a derivacao e abrir o "
    "codigo para reproducao."
)

# A text that is otherwise valid but contains a phrase a profile lists under
# `# avoid` — the deterministic validator must reject it (never publish).
FORBIDDEN_TEXT = (
    "Toda equipe de engenharia precisa de sinergia disruptiva para escalar, "
    "dizem os consultores, e eu discordo porque software bom nasce de decisao "
    "tecnica chata e nao de palavra bonita em slide de reuniao trimestral. "
    "#engenharia"
)

# C: a README feature stated in the FUTURE tense ("Kof sera a camada de
# integracao", "o design mira z/OS") asserted as ALREADY working. The digest
# labels it [documentado]; the post may not upgrade it to a running feature.
PLANNED_AS_DONE_TEXT = (
    "O projeto ja esta em producao e a integracao com a camada moderna ja "
    "funciona ponta a ponta, com o nucleo rodando em z/OS e o batch orquestrado "
    "por JCL. A arquitetura foi validada e o codigo compila sem ajustes, o que "
    "mostra maturidade do time na escolha de manter a logica de negocio no "
    "COBOL enquanto expoe uma API para os consumidores novos. Nada disso e "
    "plano, ja roda. #engenharia"
)

# K: plausible claims with NO evidence attached. The material for a projects
# pauta is a read of the repo; the post asserts a capability nobody recorded.
PLAUSIBLE_NO_EVIDENCE_TEXT = (
    "O projeto trata concorrencia com um modelo de lock otimista que evita "
    "deadlock por construcao e mantem a taxa de transferencia estavel mesmo "
    "sob pico, porque o design separa leitura de escrita de forma limpa. Isso "
    "e o tipo de decisao que so aparece quando alguem ja sofreu com contencao "
    "de recurso em producao e resolveu atacar a raiz em vez do sintoma. O "
    "resultado e um sistema previsivel. #engenharia"
)

# G: the SAME thesis as an earlier post, with different vocabulary. Used to
# prove the semantic gate catches a reworded restatement the lexical memory
# cannot see.
SAME_THESIS_A = (
    "Quebrar um monolito em microsservicos so porque esta na moda adiciona "
    "latencia de rede e custo de manutencao sem resolver gargalo real, porque "
    "a complexidade da distribuicao nao paga o proprio preco. #arquitetura"
)

SAME_THESIS_B = (
    "Adotar uma arquitetura distribuida sem necessidade traz latencia entre "
    "servicos e mais superficie de manutencao no lugar de um monolito que ja "
    "funcionava, ja que o custo da separacao nao se justifica pelo ganho. "
    "#arquitetura"
)

# H: the SAME SUBJECT with a DIFFERENT, justified conclusion. The semantic gate
# must NOT collapse these into "the same thesis" — the spec explicitly allows a
# return to a subject when the conclusion differs.
SAME_SUBJECT_OTHER_ANGLE = (
    "Microsservicos resolvem um problema real quando o gargalo e organizacional, "
    "como autonomia de times e ciclos de deploy independentes, e nesse caso a "
    "latencia extra e um preco aceitavel. O erro nao e distribuir, e distribuir "
    "sem saber qual dor a separacao ataca. #arquitetura"
)


# The four editorial FUNCTIONS (the `function:` of a `# category`). A profile
# may label its slots anything, so the fixture keys on the words the planning
# labels actually use. Distinct openings and low n-gram overlap, so the
# anti-repetition gate is not tripped between slots.
BY_FUNCTION = {
    "trabalho": (
        "A parte que de fato mudou no projeto nesta semana e a mais chata de "
        "anunciar, porque ajustar o contrato explicito entre dois modulos "
        "evitou uma classe inteira de bug que so apareceria em producao meses "
        "depois. Nada disso e bonito de contar, mas e exatamente o tipo de "
        "trabalho que sustenta o resto. #java #arquitetura"
    ),
    "noticia": (
        "Saiu hoje mais uma versao de runtime e o que me interessa nela nao e "
        "o numero da versao nem o nome bonito do recurso, e a mudanca de "
        "comportamento em como o coletor lida com objetos de vida longa, porque "
        "isso sim muda a conta de memoria de quem roda servico grande em "
        "maquina pequena. O resto do anuncio e marketing. #jvm #performance"
    ),
    "contraponto": (
        "Toda vez que aparece uma ferramenta nova alguem diz que agora nao "
        "precisa mais entender o problema, e eu discordo com todas as letras "
        "porque a ferramenta resolve a parte mecanica e deixa a parte dificil "
        "intacta, que e decidir o que o sistema deve fazer quando as coisas dao "
        "errado. Delegar isso nao acelera nada, so adia a conta. #engenharia"
    ),
    "observacao": (
        "O melhor comentario de codigo que ja li na vida nao explicava o que a "
        "linha fazia, explicava por que ela estava daquele jeito estranho, e "
        "era uma frase curta dizendo que a alternativa parecia melhor mas "
        "quebrava em um caso que ninguem mais lembra. Isso e o tipo de coisa "
        "que economiza uma tarde de alguem dois anos depois. #carreira"
    ),
}

# Two lexically DIFFERENT news drafts, alternated per call. Used by the
# same-subject/different-stance test: the fixture must not return identical
# text, or the LEXICAL anti-repetition gate discards the second draft and the
# test stops measuring the SEMANTIC gate it is about.
NEWS_VARY_A = (
    "Saiu hoje mais uma versao de runtime e o que me interessa nela nao e o "
    "numero da versao, e a mudanca de comportamento em como o coletor lida com "
    "objetos de vida longa. #jvm"
)
NEWS_VARY_C = (
    "Um projeto open source mudou de licenca essa semana e o efeito pratico "
    "nao esta no texto da licenca, esta no que acontece com quem ja embarcou o "
    "codigo e agora precisa decidir entre continuar ou trocar de dependencia. "
    "#opensource"
)
NEWS_VARY_D = (
    "Saiu um levantamento sobre quanto tempo times gastam em manutencao de "
    "build e o numero e menos interessante que a distribuicao dele, porque "
    "alguns poucos times puxam a media para cima com pipeline mal desenhado."
)


NEWS_VARY_B = (
    "Apareceu um texto novo sobre como times escolhem arquitetura e o ponto "
    "central dele e que a decisao costuma seguir o organograma antes de seguir "
    "o problema tecnico, o que explica muita separacao de servico sem dor real."
)


def pick_reply(prompt: str, mode: str) -> str:
    if mode == "forbidden":
        return FORBIDDEN_TEXT
    if mode == "repeat":
        return REPEAT_TEXT
    if mode == "episode":
        return EPISODE_TEXT
    if mode == "readclaim":
        return READCLAIM_TEXT
    if mode == "retroepisode":
        return RETRO_EPISODE_TEXT
    if mode == "localclaim":
        return LOCALCLAIM_TEXT
    if mode == "newsepisode":
        return NEWS_EPISODE_TEXT
    if mode == "actionclaim":
        return ACTIONCLAIM_TEXT
    m = re.search(r"CATEGORIA EDITORIAL DESTE HORARIO: (.*)", prompt)
    label = m.group(1).lower() if m else ""
    # Scoped to the PROJECTS slot: this mode exists to prove the repo-origin
    # test-guarantee check fires, and every other slot must keep producing its
    # own distinct text or the anti-repetition gate discards them first.
    if mode == "testclaim" and "trabalho" in label:
        return TESTCLAIM_TEXT
    if mode == "testclaimdenial" and "trabalho" in label:
        return TESTCLAIM_DENIAL_TEXT
    if mode == "testclaimembora" and "trabalho" in label:
        return TESTCLAIM_EMBORA_TEXT
    if mode == "absenceclaim" and "noticia" in label:
        return ABSENCE_CLAIM_TEXT
    if mode == "hardwareclaim" and "noticia" in label:
        return HARDWARE_CLAIM_TEXT
    if mode == "reactionclaim" and "noticia" in label:
        return REACTION_CLAIM_TEXT
    if mode == "unverifiedclaim" and "trabalho" in label:
        return UNVERIFIED_CLAIM_TEXT
    if mode == "headlineonly":
        return HEADLINE_ONLY_TEXT
    if mode == "compilernoun":
        return COMPILER_NOUN_TEXT
    if mode == "kofnosign":
        return KOF_NO_SIGNATURE_TEXT
    if mode == "kofbanknosign":
        return KOFBANK_NO_SIGNATURE_TEXT
    if mode == "episodeboundary":
        return EPISODE_BOUNDARY_TEXT
    if mode == "paragraphs":
        return PARAGRAPH_TEXT
    if mode == "encounter" and "trabalho" in label:
        return ENCOUNTER_TEXT
    if mode == "planneddone" and "trabalho" in label:
        return PLANNED_AS_DONE_TEXT
    if mode == "plausible" and "trabalho" in label:
        return PLAUSIBLE_NO_EVIDENCE_TEXT
    # Semantic repetition: the SECOND call returns the reworded restatement of
    # the first, so a run that plans two opinion slots hits the thesis gate on
    # the second. Keyed on a call counter, not on the label, because the point
    # is that two DIFFERENT slots argue the same thing.
    if mode == "samethesis":
        pick_reply.calls = getattr(pick_reply, "calls", 0) + 1
        if pick_reply.calls == 1:
            return SAME_THESIS_A
        return SAME_THESIS_B
    if mode == "newsvary":
        # The draft is derived from the TOPIC in the prompt, so it is stable for
        # a given candidate and DIFFERENT across candidates — and, crucially, it
        # survives across processes. A per-process call counter resets when the
        # test invokes `plan` a second time (a new JVM), which made the fixture
        # repeat the same text and tripped the LEXICAL gate instead of the check
        # under test.
        pool = [NEWS_VARY_A, NEWS_VARY_B, NEWS_VARY_C, NEWS_VARY_D]
        # Deterministic (Python's builtin hash() is randomised per process by
        # PYTHONHASHSEED, which would make the fixture unstable).
        acc = 0
        for ch in prompt:
            acc = (acc * 31 + ord(ch)) % 1000003
        return pool[acc % len(pool)]
    if mode == "samesubject":
        pick_reply.calls = getattr(pick_reply, "calls", 0) + 1
        if pick_reply.calls == 1:
            return SAME_THESIS_A
        return SAME_SUBJECT_OTHER_ANGLE
    for key, text in BY_CATEGORY.items():
        if key in label:
            return text
    for key, text in BY_FUNCTION.items():
        if key in label:
            return text
    return REPEAT_TEXT


class Handler(BaseHTTPRequestHandler):
    mode = "distinct"

    def _json(self, payload: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/api/tags":
            self._json(json.dumps({"models": [{"name": "fake-lm"}]}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_response(404)
            self.end_headers()
            return
        n = int(self.headers.get("Content-Length", "0"))
        req = json.loads(self.rfile.read(n) or b"{}")
        text = ""
        for msg in req.get("messages", []):
            text += msg.get("content", "") + "\n"
        # Dump the exact prompt the pipeline built (evidence for the report /
        # manual inspection); never used by the Kof side.
        try:
            with open("prompts.log", "a", encoding="utf-8") as fh:
                fh.write("===== PROMPT =====\n" + text + "\n")
        except OSError:
            pass
        resp = {
            "model": req.get("model", "fake-lm"),
            "created_at": "2026-01-01T00:00:00Z",
            "message": {"role": "assistant", "content": pick_reply(text, self.mode)},
            "done": True,
            "done_reason": "stop",
        }
        self._json(json.dumps(resp).encode())

    def log_message(self, fmt, *args):
        sys.stderr.write("fake_lm_personal: " + (fmt % args) + "\n")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11581
    Handler.mode = sys.argv[2] if len(sys.argv) > 2 else "distinct"
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
