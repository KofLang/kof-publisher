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
    m = re.search(r"CATEGORIA EDITORIAL DESTE HORARIO: (.*)", prompt)
    label = m.group(1).lower() if m else ""
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
