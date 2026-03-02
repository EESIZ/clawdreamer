#!/usr/bin/env bash
# session-flush.sh — Send /new to main agent to flush session memory
# Run via cron at 02:00 KST, before Dreamer (03:00 KST)

set -euo pipefail

export XDG_RUNTIME_DIR=/run/user/1001
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus

# Read OpenAI key from auth.json (needed for config resolution)
OPENAI_API_KEY=$(python3 -c "
import json
with open('/home/g158khs/.openclaw/agents/main/agent/auth.json') as f:
    print(json.load(f)['openai']['key'])
")
export OPENAI_API_KEY

openclaw agent -m '/new' --agent main --timeout 30 > /dev/null 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S KST') session-flush: /new sent" >> /home/g158khs/.openclaw/workspace/dreamer/dream-log/cron.log
