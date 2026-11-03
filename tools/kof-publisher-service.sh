#!/usr/bin/env bash
# KOF publisher — sobe o daemon editorial com TODO o ambiente necessario.
#
# Por que isto existe: o daemon herda o ambiente do processo que o inicia. As
# credenciais (LM, LinkedIn) e os ajustes de retry NAO vivem em arquivo de
# configuracao nenhum — se alguem rodar `publisher start` a mao, sem dar source
# nos arquivos de segredo, o daemon sobe sem token e com a janela de retry
# curta do codigo (~6s, que ja perdeu um post do dia por oscilacao de rede).
# Este script e o start reproduzivel: mesma coisa, sempre.
#
# Uso:
#   tools/kof-publisher-service.sh start|stop|status|logs
set -euo pipefail

PUB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_KOF="${KOF_PUBLISHER_HOME:-$HOME/.kof/publisher}"
STORE="${KOF_PUBLISHER_STORE:-$HOME_KOF/publisher.db}"
COMPANY="${KOF_PUBLISHER_COMPANY:-$PUB/examples/mel.kofmd}"
JARS="$HOME/.local/share/kof/lib/kof.jar:$HOME/.kof/deps/org/xerial/sqlite-jdbc/3.53.4.0/sqlite-jdbc-3.53.4.0.jar"

JAVA_BIN=""
for c in "${JAVA_HOME:-}/bin/java" "$HOME/.sdkman/candidates/java/current/bin/java"; do
    if [ -n "$c" ] && [ -x "$c" ]; then JAVA_BIN="$c"; break; fi
done
if [ -z "$JAVA_BIN" ]; then JAVA_BIN="$(command -v java 2>/dev/null || true)"; fi
if [ -z "$JAVA_BIN" ]; then echo "ERRO: java nao encontrado" >&2; exit 1; fi

export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

# Segredos: os mesmos arquivos que o resto do projeto usa (600).
for f in "$HOME/.local/share/kof/kof-lm.env" \
         "$HOME/.local/share/kof/linkedin-secrets.env" \
         "$HOME/.local/share/kof/github-secrets.env"; do
    [ -f "$f" ] && { # shellcheck disable=SC1090
        source "$f"; }
done
[ -n "${KOF_GITHUB_TOKEN:-}" ] && export KOF_GITHUB_TOKEN

# Publicar no PROPRIO perfil exige opt-in explicito (o publisher recusa sem
# isto, de proposito). Fica no ambiente do processo, nunca no perfil/banco.
export KOF_LINKEDIN_ALLOW_PERSONAL="${KOF_LINKEDIN_ALLOW_PERSONAL:-true}"

# Janela de retry da publicacao, MAIOR que o default do codigo: 5 tentativas
# com 10s dobrando (~2min30). O default (3 x 2s = ~6s) nao cobre uma oscilacao
# real de rede — medido em 2026-10-12, quando um post do dia foi perdido.
export KOF_PUBLISHER_ATTEMPTS="${KOF_PUBLISHER_ATTEMPTS:-5}"
export KOF_PUBLISHER_ATTEMPT_DELAY_MS="${KOF_PUBLISHER_ATTEMPT_DELAY_MS:-10000}"

# Retentativa do HORARIO: se um slot nao conseguiu postar (sem material, ou
# gate factual barrou), ele tenta de novo mais tarde no mesmo dia, ate 3 vezes.
export KOF_PUBLISHER_RETRY_MAX="${KOF_PUBLISHER_RETRY_MAX:-3}"
export KOF_PUBLISHER_RETRY_DELAY_MIN="${KOF_PUBLISHER_RETRY_DELAY_MIN:-20}"

# Cooldown de ASSUNTO: quantos itens editoriais recentes olhar para decidir se
# um assunto (IA, arquitetura...) esta repetido. 4 = "nao dois dias seguidos"
# com 4 posts por dia. 0 desliga.
export KOF_PUBLISHER_SUBJECT_WINDOW="${KOF_PUBLISHER_SUBJECT_WINDOW:-4}"

# Preparo com antecedencia: gera o texto `prep.lead.min` antes do horario e
# publica na hora exata. Se a geracao falhar na janela, tenta de novo em
# `prep.retry.min` (curto), para ainda pegar a hora.
export KOF_PUBLISHER_PREP_LEAD_MIN="${KOF_PUBLISHER_PREP_LEAD_MIN:-10}"
export KOF_PUBLISHER_PREP_RETRY_MIN="${KOF_PUBLISHER_PREP_RETRY_MIN:-3}"

# ESPELHO DO ENOIS — implementado e testado, mas DESLIGADO por padrao: o modo
# ativo e a agenda por horario (06/12/15/18). Para religar o espelho, suba o
# daemon com KOF_ENOIS_POLL_MIN=10 e remova as agendas (publisher cancel <nome>).
export KOF_ENOIS_USERNAME="${KOF_ENOIS_USERNAME:-aminadojava}"
export KOF_ENOIS_POLL_MIN="${KOF_ENOIS_POLL_MIN:-0}"
export KOF_ENOIS_MIN_CHARS="${KOF_ENOIS_MIN_CHARS:-40}"
export KOF_ENOIS_MAX_PER_POLL="${KOF_ENOIS_MAX_PER_POLL:-2}"

export KOF_PUBLISHER_HOME="$HOME_KOF"
cd "$PUB"

run() { exec "$JAVA_BIN" -cp "build/classes:$JARS" Default.Main "$@" --company "$COMPANY" --store "$STORE"; }

case "${1:-status}" in
    start)  run start ;;
    stop)   run stop ;;
    status) run status ;;
    logs)   exec tail -n "${2:-40}" -f "$HOME_KOF/publisher.log" ;;
    *)      echo "uso: $0 start|stop|status|logs [n]" >&2; exit 2 ;;
esac
