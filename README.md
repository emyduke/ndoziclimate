# Ndozi Climate

AI-powered climate risk assessment platform for Nigerian real estate and infrastructure.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Local Development (without Docker)](#local-development-without-docker)
- [Docker Deployment (Production)](#docker-deployment-production)
  - [Step 1 — Server Preparation](#step-1--server-preparation)
  - [Step 2 — Install Dependencies on the Server](#step-2--install-dependencies-on-the-server)
  - [Step 3 — Clone the Repository](#step-3--clone-the-repository)
  - [Step 4 — Configure Environment Variables](#step-4--configure-environment-variables)
  - [Step 5 — Add the GEE Service Account Key](#step-5--add-the-gee-service-account-key)
  - [Step 6 — Build Docker Images](#step-6--build-docker-images)
  - [Step 7 — Create Host Directories](#step-7--create-host-directories)
  - [Step 8 — Start All Services](#step-8--start-all-services)
  - [Step 9 — Create a Django Superuser](#step-9--create-a-django-superuser)
  - [Step 10 — Configure Nginx](#step-10--configure-nginx)
  - [Step 11 — Obtain SSL Certificate](#step-11--obtain-ssl-certificate)
  - [Step 12 — Verify the Deployment](#step-12--verify-the-deployment)
- [Subsequent Deployments (Updates)](#subsequent-deployments-updates)
- [Useful Docker Commands](#useful-docker-commands)
- [Environment Variables Reference](#environment-variables-reference)
- [Architecture](#architecture)

---

## Overview

Ndozi Climate is a Django application that provides:
- Climate risk assessments powered by Google Earth Engine (GEE) pipelines
- AI narrative generation via Anthropic Claude
- Admin portal for user and assessment management
- Authenticated dashboard for end-users

**Stack:** Django 4.2 · MySQL 8 · Redis 7 · Gunicorn · Nginx · Docker

---

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Docker | 24.x |
| Docker Compose plugin | v2.x (`docker compose`) |
| Ubuntu / Debian server | 22.04 LTS recommended |
| Nginx (on host) | 1.18+ |
| Certbot | Any recent version |
| Python (local dev only) | 3.11+ |

---

## Project Structure

```
ndozi_climate/          ← Django project root (all commands run from here)
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── manage.py
├── requirements.txt
├── core/               ← Main Django app
├── ndozi_climate/      ← Django settings package
│   └── settings/
│       ├── base.py
│       ├── development.py
│       └── production.py
├── templates/
├── static/
└── deploy/
    ├── deploy.sh       ← One-command deployment script
    ├── gunicorn.conf.py
    └── nginx/
        └── ndozi_climate.conf
```

---

## Local Development (without Docker)

```bash
cd ndozi_climate

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env: set DJANGO_SETTINGS_MODULE=ndozi_climate.settings.development
# Development uses SQLite and in-memory cache — no MySQL or Redis needed.

# Run migrations and start the dev server
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000

---

## Docker Deployment (Production)

The production stack runs three containers — `web` (Django/Gunicorn), `db` (MySQL 8), and `redis` (Redis 7) — managed by Docker Compose. Nginx runs **on the host** and reverse-proxies to the `web` container.

### Step 1 — Server Preparation

Provision a Ubuntu 22.04 LTS server. Ensure ports 80 and 443 are open in your firewall.

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

### Step 2 — Install Dependencies on the Server

```bash
# Docker (official install script)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # allow running docker without sudo (re-login after)

# Nginx
sudo apt-get install -y nginx

# Certbot (for Let's Encrypt SSL)
sudo apt-get install -y certbot python3-certbot-nginx
```

Log out and back in so the `docker` group takes effect.

### Step 3 — Clone the Repository

```bash
git clone https://github.com/your-org/ndozi-climate.git /opt/ndozi-climate
cd /opt/ndozi-climate/ndozi_climate
```

> All subsequent commands assume you are inside the `ndozi_climate/` directory (where `docker-compose.yml` lives).

### Step 4 — Configure Environment Variables

```bash
cp .env.example .env
nano .env   # or your preferred editor
```

Fill in **every value** — pay special attention to:

| Variable | What to set |
|---|---|
| `DJANGO_SECRET_KEY` | Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `MYSQL_ROOT_PASSWORD` | A strong random password |
| `DB_PASSWORD` | A different strong password for the app DB user |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `GEE_PROJECT_ID` | Your Google Earth Engine project ID |
| `GEE_SERVICE_ACCOUNT_KEY` | Path inside the container: `/run/gee/service-account.json` |
| `ALLOWED_HOSTS` | `ndoziclimate.org,www.ndoziclimate.org` |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP credentials |

> **Never commit `.env` to version control.**

### Step 5 — Add the GEE Service Account Key

The GEE service account JSON key must be available inside the `web` container. Mount it from the host:

1. Copy your GEE service account JSON file to the server:
   ```bash
   scp your-gee-key.json user@your-server:/opt/ndozi_climate/gee-service-account.json
   chmod 600 /opt/ndozi_climate/gee-service-account.json
   ```

2. Add a volume mount to `docker-compose.yml` under the `web` service (or manage it as a Docker secret):
   ```yaml
   volumes:
     - /opt/ndozi_climate/gee-service-account.json:/run/gee/service-account.json:ro
   ```

3. Confirm `GEE_SERVICE_ACCOUNT_KEY=/run/gee/service-account.json` in your `.env`.

### Step 6 — Build Docker Images

```bash
docker compose build
```

This builds the `web` image using the `Dockerfile` in the project root. MySQL and Redis use pre-built images from Docker Hub.

### Step 7 — Create Host Directories

Docker bind-mounts the static files and media directories to the host so Nginx can serve them directly.

```bash
sudo mkdir -p /opt/ndozi_climate/staticfiles
sudo mkdir -p /opt/ndozi_climate/media
sudo chmod -R 755 /opt/ndozi_climate
```

### Step 8 — Start All Services

```bash
docker compose up -d
```

This will:
- Start `db` (MySQL) and `redis`
- Wait for both to be healthy
- Start `web`, run `migrate`, run `collectstatic`, then start Gunicorn on port 8000 (bound to `127.0.0.1`)

Check that all containers are running:
```bash
docker compose ps
```

Watch the startup logs:
```bash
docker compose logs -f web
```

You should see `Booting worker` lines from Gunicorn indicating a successful start.

### Step 9 — Create a Django Superuser

```bash
docker compose exec web python manage.py createsuperuser
```

Follow the prompts to set a username, email, and password.

### Step 10 — Configure Nginx

```bash
sudo cp deploy/nginx/ndozi_climate.conf /etc/nginx/sites-available/ndozi_climate
sudo ln -s /etc/nginx/sites-available/ndozi_climate /etc/nginx/sites-enabled/ndozi_climate

# Remove the default site if it exists
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t     # confirm no syntax errors
sudo systemctl reload nginx
```

At this point the site is accessible over HTTP on port 80 (before SSL).

### Step 11 — Obtain SSL Certificate

```bash
sudo certbot --nginx -d ndoziclimate.org -d www.ndoziclimate.org
```

Certbot will automatically update the nginx config with SSL directives and set up auto-renewal. Test renewal:
```bash
sudo certbot renew --dry-run
```

### Step 12 — Verify the Deployment

```bash
# Django system checks (security, database, etc.)
docker compose exec web python manage.py check --deploy

# Smoke-test the live site
curl -I https://ndoziclimate.org
curl -I https://ndoziclimate.org/api/
```

Expected: `HTTP/2 200` for the home page and API. Visit the admin at https://ndoziclimate.org/admin/ and the portal at https://ndoziclimate.org/portal/.

---

## Subsequent Deployments (Updates)

Use the provided deployment script for all future updates:

```bash
cd /opt/ndozi-climate/ndozi_climate

git pull

# Full rebuild + redeploy
./deploy/deploy.sh

# Or, if only config/templates changed (no dependency changes):
./deploy/deploy.sh --skip-build
```

The script will: build updated images → stop old containers → start new ones → run migrations + collectstatic → reload nginx.

---

## Useful Docker Commands

```bash
# View live logs for the web container
docker compose logs -f web

# Open a Django shell
docker compose exec web python manage.py shell

# Run a management command
docker compose exec web python manage.py <command>

# Stop all containers (data is preserved in volumes)
docker compose down

# Stop and delete all volumes (⚠️ destroys all DB data)
docker compose down -v

# Rebuild a single service
docker compose build web
docker compose up -d --no-deps web

# View resource usage
docker stats
```

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | Django secret key — must be long and random in production |
| `DJANGO_SETTINGS_MODULE` | Yes | Set to `ndozi_climate.settings.production` |
| `ALLOWED_HOSTS` | Yes | Comma-separated list of allowed hostnames |
| `CORS_ALLOWED_ORIGINS` | Yes | Comma-separated list of allowed origins |
| `MYSQL_ROOT_PASSWORD` | Yes | MySQL root password (used by Docker Compose) |
| `DB_NAME` | Yes | Database name (default: `ndozi_climate`) |
| `DB_USER` | Yes | Database user |
| `DB_PASSWORD` | Yes | Database password |
| `ANTHROPIC_API_KEY` | Yes | Key for Claude AI narrative generation |
| `GEE_SERVICE_ACCOUNT_KEY` | Yes | Path to GEE service account JSON inside the container |
| `GEE_PROJECT_ID` | Yes | Google Earth Engine project ID |
| `EMAIL_BACKEND` | No | Django email backend class |
| `EMAIL_HOST` | No | SMTP host (default: `smtp.gmail.com`) |
| `EMAIL_PORT` | No | SMTP port (default: `587`) |
| `EMAIL_USE_TLS` | No | Use TLS (default: `True`) |
| `EMAIL_HOST_USER` | No | SMTP username |
| `EMAIL_HOST_PASSWORD` | No | SMTP password / app password |
| `DEFAULT_FROM_EMAIL` | No | From address for outgoing emails |
| `ADMIN_EMAIL` | No | Admin notification recipient |

> `DB_HOST`, `DB_PORT`, and `REDIS_URL` are injected by Docker Compose and should **not** be set in `.env`.

---

## Architecture

```
Internet
   │
   ▼
Nginx (host, port 443)
   │  /static/  → /opt/ndozi_climate/staticfiles/  (bind-mount)
   │  /media/   → /opt/ndozi_climate/media/         (bind-mount)
   │  /*        → proxy_pass http://127.0.0.1:8000
   │
   ▼
web container (Gunicorn, port 8000)
   │
   ├── db container  (MySQL 8, named volume)
   └── redis container (Redis 7, named volume)
```

All three containers share the `ndozi` Docker bridge network. Only the `web` container exposes a port (bound to `127.0.0.1:8000`) — `db` and `redis` are not reachable from outside the Docker network.
