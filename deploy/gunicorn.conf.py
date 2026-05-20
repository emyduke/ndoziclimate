"""
Gunicorn configuration — production settings.
Mounted into the backend container at /app/gunicorn.conf.py via docker-compose volume.
Changes here take effect with: docker compose restart backend
"""
import multiprocessing

# ── Binding ──────────────────────────────────────────────────────────────────
bind = "0.0.0.0:8000"
backlog = 2048

# ── Workers ──────────────────────────────────────────────────────────────────
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
graceful_timeout = 90
keepalive = 5

# ── Reliability ──────────────────────────────────────────────────────────────
max_requests = 1000
max_requests_jitter = 100
preload_app = True

# ── Logging ──────────────────────────────────────────────────────────────────
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sus'

# ── Security ─────────────────────────────────────────────────────────────────
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
