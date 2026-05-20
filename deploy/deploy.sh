#!/usr/bin/env bash
# deploy.sh — Ndozi Climate production deployment
#
# Usage:
#   ./deploy/deploy.sh               # full build + deploy
#   ./deploy/deploy.sh --skip-build  # restart containers without rebuilding
#
# Run from the ndozi_climate/ project directory (where docker-compose.yml lives).
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="$PROJECT_ROOT/deploy"
cd "$PROJECT_ROOT"

# ── Helpers ──────────────────────────────────────────────────────────────────
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

[[ -f .env ]] || die ".env not found — copy .env.example and fill in real values first."

# ── Nginx: install config if not already in place ────────────────────────────
NGINX_AVAILABLE="/etc/nginx/sites-available/ndozi_climate"
NGINX_ENABLED="/etc/nginx/sites-enabled/ndozi_climate"
if command -v nginx &>/dev/null; then
  if [[ ! -f "$NGINX_AVAILABLE" ]]; then
    log "Installing nginx config..."
    sudo cp "$DEPLOY_DIR/nginx/ndozi_climate.conf" "$NGINX_AVAILABLE"
    sudo ln -sf "$NGINX_AVAILABLE" "$NGINX_ENABLED"
    log "nginx config installed — run: sudo certbot --nginx -d ndoziclimate.org -d www.ndoziclimate.org"
  fi
fi

# ── Build ────────────────────────────────────────────────────────────────────
if [[ "${1:-}" != "--skip-build" ]]; then
  log "Building Docker images..."
  docker compose build
fi

# ── Ensure host directories exist for Docker bind-mounts ─────────────────────
log "Creating host directories..."
mkdir -p /opt/ndozi_climate/staticfiles
mkdir -p /opt/ndozi_climate/media
chmod -R 755 /opt/ndozi_climate

# ── Deploy ───────────────────────────────────────────────────────────────────
log "Stopping old containers..."
docker compose down --remove-orphans

log "Starting services..."
docker compose up -d

# ── Wait for web service to be ready ─────────────────────────────────────────
log "Waiting for web service to start (20s)..."
sleep 20

# ── Sanity checks ────────────────────────────────────────────────────────────
log "Container status:"
docker compose ps

log "Running Django deploy checks..."
docker compose exec web python manage.py check --deploy

# ── Reload system nginx ──────────────────────────────────────────────────────
if command -v nginx &>/dev/null; then
  log "Reloading nginx..."
  sudo nginx -t && sudo systemctl reload nginx
fi

log ""
log "✅ Ndozi Climate deployed successfully!"
log "   Site:    https://ndoziclimate.org"
log "   API:     https://ndoziclimate.org/api/"
log "   Admin:   https://ndoziclimate.org/admin/"
log "   Portal:  https://ndoziclimate.org/portal/"

