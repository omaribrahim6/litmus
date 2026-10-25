#!/usr/bin/env bash
# Push the working tree to the VPS and rebuild the worker (works while the repo is private).
# Run from WSL at the repo root:  bash deploy/sync-to-vps.sh
set -euo pipefail
HOST=${VPS:-altair@23.95.188.69}
cd "$(dirname "$0")/.."
rsync -az --delete -e "ssh -o BatchMode=yes" \
  --exclude .git --exclude .env --exclude '.env.*' --exclude node_modules --exclude .next \
  --exclude '.venv' --exclude '__pycache__' --exclude worker/media --exclude station/data \
  --exclude web --exclude data --exclude deploy/secrets --exclude deploy/.env.vps \
  ./ "$HOST":litmus/
ssh -o BatchMode=yes "$HOST" "SKIP_PULL=1 bash ~/litmus/deploy/vps-up.sh"
