#!/usr/bin/env bash
# KOF Lab daily post: refresh lab, generate from the REAL facts, publish to
# LinkedIn. Intended for cron/systemd-timer at 09:30 (or run by hand).
# Requires: tools/linked_oauth.py done once (secrets env), Ollama running.
set -euo pipefail

PUB="/home/mel/Documentos/kof-publisher"
REPO="/home/mel/Documentos/Kof4j"
JARS="$HOME/.local/share/kof/lib/kof.jar:$HOME/.kof/deps/org/xerial/sqlite-jdbc/3.53.4.0/sqlite-jdbc-3.53.4.0.jar"

source "$HOME/.local/share/kof/linkedin-secrets.env"

# the digest is only honest if origin/lab is current
git -C "$REPO" fetch origin lab --quiet

cd "$PUB"
mkdir -p var
KOF_LM_MODEL="${KOF_LM_MODEL:-qwen3.5:0.8b}" \
KOF_LM_TOKENS="${KOF_LM_TOKENS:-700}" \
KOF_LM_TIMEOUT="${KOF_LM_TIMEOUT:-900}" \
exec java -cp "build/classes:$JARS" Default.Main \
  generate --company examples/kof-lab.kofmd \
           --store "$PUB/var/koflab.db" \
           --topic "novidades da lab" \
           --target linkedin \
           --publish-ok
