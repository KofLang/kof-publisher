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

# A text that is otherwise valid but contains a phrase a profile lists under
# `# avoid` — the deterministic validator must reject it (never publish).
FORBIDDEN_TEXT = (
    "Toda equipe de engenharia precisa de sinergia disruptiva para escalar, "
    "dizem os consultores, e eu discordo porque software bom nasce de decisao "
    "tecnica chata e nao de palavra bonita em slide de reuniao trimestral. "
    "#engenharia"
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
    if mode == "reactionclaim" and "noticia" in label:
        return REACTION_CLAIM_TEXT
    if mode == "unverifiedclaim" and "trabalho" in label:
        return UNVERIFIED_CLAIM_TEXT
    if mode == "encounter" and "trabalho" in label:
        return ENCOUNTER_TEXT
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
