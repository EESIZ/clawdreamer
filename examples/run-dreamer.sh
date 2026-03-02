#!/bin/bash
# Dreamer daily run wrapper
# Cron example: 0 3 * * * /path/to/dreamer/examples/run-dreamer.sh

set -euo pipefail

export DREAMER_HOME="${DREAMER_HOME:-$HOME/.dreamer}"

# Load API keys from .env
if [ -f "$HOME/.env" ]; then
    set -a
    source "$HOME/.env"
    set +a
fi

cd "$(dirname "$0")/.."
python3 dreamer.py --verbose >> "$DREAMER_HOME/dream-log/cron.log" 2>&1
