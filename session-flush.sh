#!/usr/bin/env bash
# session-flush.sh — Send /new to main agent to flush session memory
# Run via cron at 02:00 KST, before Dreamer (03:00 KST)

set -euo pipefail

export OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
export DREAMER_HOME="${DREAMER_HOME:-$HOME/.dreamer}"

uid="$(id -u)"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$uid}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"

# Read OpenAI key from auth.json (needed for config resolution)
OPENAI_API_KEY=$(python3 -c "
import json
import os
auth_path = os.path.join(os.environ['OPENCLAW_HOME'], 'agents/main/agent/auth.json')
with open(auth_path) as f:
    print(json.load(f)['openai']['key'])
")
export OPENAI_API_KEY

openclaw agent -m '/new' --agent main --timeout 30 > /dev/null 2>&1

mkdir -p "$DREAMER_HOME/dream-log"
echo "$(date '+%Y-%m-%d %H:%M:%S KST') session-flush: /new sent" >> "$DREAMER_HOME/dream-log/cron.log"
