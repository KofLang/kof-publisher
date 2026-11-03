#!/usr/bin/env bash
# KOF publisher — atualiza a BASE DE CONHECIMENTO dos repositorios (GitHub).
#
# Por que isto existe: o daemon NAO consulta o GitHub sozinho. Ele le o que o
# comando `github` ja persistiu (a tabela `repostate`, que e INCREMENTAL — um
# repo cujo pushed_at nao mudou nao e relido). Sem esta atualizacao periodica, o
# slot das 06:00 (trabalho real e projetos) ve o retrato do dia anterior e
# publica sobre uma atividade que ja nao e mais a mais recente.
#
# Roda ANTES das 06:00 (o timer/cron chama as 05:30). Nada e publicado aqui:
# o comando e somente leitura e apenas grava o que ENCONTROU.
#
# Configuracao POR USUARIO (nada hardcoded de credencial):
#   ~/.local/share/kof/github-secrets.env   -> KOF_GITHUB_TOKEN
#   (sem esse arquivo, cai no `gh auth token` do próprio gh CLI)
#   KOF_GITHUB_REFRESH_LIMIT   (default 20)
#   KOF_PUBLISHER_HOME|STORE|COMPANY  (defaults abaixo)
set -euo pipefail

PUB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_KOF="${HOME}/.kof/publisher"
STORE="${KOF_PUBLISHER_STORE:-$HOME_KOF/publisher.db}"
COMPANY="${KOF_PUBLISHER_COMPANY:-$PUB/examples/mel.kofmd}"
LIMIT="${KOF_GITHUB_REFRESH_LIMIT:-20}"
JARS="$HOME/.local/share/kof/lib/kof.jar:$HOME/.kof/deps/org/xerial/sqlite-jdbc/3.53.4.0/sqlite-jdbc-3.53.4.0.jar"

# Token: arquivo local primeiro (funciona sem sessao/gnome-keyring), `gh` depois.
if [ -f "$HOME/.local/share/kof/github-secrets.env" ]; then
    # shellcheck disable=SC1090
    source "$HOME/.local/share/kof/github-secrets.env"
fi
if [ -z "${KOF_GITHUB_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then
    KOF_GITHUB_TOKEN="$(gh auth token 2>/dev/null || true)"
fi
if [ -z "${KOF_GITHUB_TOKEN:-}" ]; then
    echo "$(date '+%F %T') AVISO: sem KOF_GITHUB_TOKEN — a API publica funciona, mas com rate limit baixo" >&2
fi

export KOF_GITHUB_TOKEN="${KOF_GITHUB_TOKEN:-}"
export KOF_PUBLISHER_HOME="${KOF_PUBLISHER_HOME:-$HOME_KOF}"

# Cron roda sem LANG: sem isto o texto sai com "?" no lugar de acentos ("—",
# "até"). C.UTF-8 mantem o log legivel e nao depende de locale instalado.
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

# `java` NAO esta no PATH minimo do cron (o runtime vem do sdkman) — medido:
# sob `env -i HOME=... PATH=/usr/bin:/bin` o exec falhava com "java: not found".
# Resolve o binario explicitamente, como o proprio Service.kf faz a partir de
# java.home, com o sdkman (symlink "current") como proximo candidato.
JAVA_BIN=""
for c in "${JAVA_HOME:-}/bin/java" "$HOME/.sdkman/candidates/java/current/bin/java"; do
    if [ -n "$c" ] && [ -x "$c" ]; then
        JAVA_BIN="$c"
        break
    fi
done
if [ -z "$JAVA_BIN" ]; then
    JAVA_BIN="$(command -v java 2>/dev/null || true)"
fi
if [ -z "$JAVA_BIN" ] || [ ! -x "$JAVA_BIN" ]; then
    echo "$(date '+%F %T') ERRO: java nao encontrado (JAVA_HOME, sdkman e PATH falharam)" >&2
    exit 1
fi

mkdir -p "$(dirname "$STORE")"
cd "$PUB"

# --force ausente de proposito: a analise e incremental e so relê o que mudou.
echo "===== $(date '+%F %T %Z') refresh do GitHub (base de conhecimento dos repos) ====="
exec "$JAVA_BIN" -cp "build/classes:$JARS" Default.Main github \
  --limit "$LIMIT" \
  --company "$COMPANY" \
  --store "$STORE"
