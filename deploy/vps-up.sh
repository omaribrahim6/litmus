#!/usr/bin/env bash
# Build and (re)start the Litmus worker on the VPS behind nginx-proxy.
#   ssh altair@23.95.188.69 'bash ~/litmus/deploy/vps-up.sh'
set -euo pipefail
cd "$(dirname "$0")"
git -C .. pull -q --ff-only || true

HOST=$(grep '^LITMUS_HOST=' .env.vps | cut -d= -f2)

# Per-host proxy settings: large uploads (videos, frames) and long Gemini calls.
docker exec nginx-proxy sh -c "printf 'client_max_body_size 300m;\nproxy_read_timeout 300s;\nproxy_send_timeout 300s;\n' > /etc/nginx/vhost.d/$HOST"

docker compose --env-file .env.vps up -d --build
sleep 4
docker ps --filter name=litmus_worker --format '{{.Names}} {{.Status}}'
docker logs --tail 5 litmus_worker
echo "health: https://$HOST/health"
