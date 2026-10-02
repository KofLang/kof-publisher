#!/usr/bin/env bash
# KOF Lab daily post — AUTOMATICO, sem etapa manual.
# Extrai os fatos da lab, gera no LM configurado, valida no estilo da autora
# e publica no alvo configurado (pagina via Community Management OU perfil
# quando o operador assumiu isso explicitamente). Falta de credencial ou de
# novidade encerra com erro/exit honesto — nunca posta nada inventado.
#
# Configuracao POR USUARIO (nada hardcoded aqui):
#   kof.config no repositorio (~/.config/kof/kof.config, ou arquivo ao lado)
#   ou env KOF_* — chaves:
#     lm.url lm.model lm.api.key            (openai-style se URL tem /v1)
#     linkedin.access.token linkedin.author.urn
#     linkedin.allow.personal=true          (so quem quer postar no proprio perfil)
#     publisher.home publisher.store publisher.dryrun.dir
#     koflab.repo      checkout do Kof4j (tambem via source_repo: $KOF_KOF4J_REPO)
#     koflab.company   caminho do .kofmd editorial
#     koflab.target    linkedin (default) | dryrun
set -euo pipefail

PUB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPANY="${KOF_KOF4J_COMPANY:-$PUB/examples/kof-lab.kofmd}"
STORE="${KOF_PUBLISHER_STORE:-${XDG_DATA_HOME:-$HOME/.local/share}/kof-publisher/koflab.db}"
JARS="$HOME/.local/share/kof/lib/kof.jar:$HOME/.kof/deps/org/xerial/sqlite-jdbc/3.53.4.0/sqlite-jdbc-3.53.4.0.jar"
KOF4J_REPO="${KOF_KOF4J_REPO:-}"

# segredos locais continuam opcionais: quem usa kof.config ja esta coberto
for f in "$HOME/.local/share/kof/linkedin-secrets.env" "$HOME/.local/share/kof/kof-lm.env"; do
    [ -f "$f" ] && # shellcheck disable=SC1090
        source "$f"
done

if [ -n "$KOF4J_REPO" ]; then
    export KOF_KOF4J_REPO   # o source_repo do .kofmd expande $KOF_KOF4J_REPO
    [ -d "$KOF4J_REPO/.git" ] && git -C "$KOF4J_REPO" fetch origin lab --quiet || true
fi

mkdir -p "$(dirname "$STORE")"
cd "$PUB"
exec java -cp "build/classes:$JARS" Default.Main \
  generate --company "$COMPANY" \
           --store "$STORE" \
           --topic "novidades da lab" \
           --target "${KOF_PUBLISH_TARGET:-linkedin}" \
           --publish-ok
