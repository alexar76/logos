# LOGOS — federation analytics engine
# Build FROM THE MONOREPO ROOT so oracles/core is in context:
#     docker build -f logos/Dockerfile -t logos .

# ── Stage 1: frontend build ──────────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder
WORKDIR /src
COPY logos/frontend/package.json logos/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund
COPY logos/frontend/ ./
RUN npm run build

# ── Stage 2: backend + nginx ─────────────────────────────────────────────────
FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx curl supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy monorepo deps
COPY oracles/core /app/core
COPY logos /app/logos

# Install Python deps
RUN pip install --no-cache-dir -e /app/core -e /app/logos

# Frontend from build stage
COPY --from=frontend-builder /src/dist /usr/share/nginx/html

# Nginx config
COPY logos/nginx.conf /etc/nginx/sites-enabled/default

# Supervisor config — run both nginx + uvicorn.  Log/pid paths are explicit and
# under /tmp: supervisord's defaults land in root-owned directories, and this
# image drops to a non-root user below.
RUN printf '%s\n' \
    '[supervisord]' \
    'nodaemon=true' \
    'logfile=/tmp/supervisord.log' \
    'pidfile=/tmp/supervisord.pid' \
    '' \
    '[program:nginx]' \
    'command=nginx -g "daemon off;"' \
    'autorestart=true' \
    'stdout_logfile=/dev/stdout' \
    'stdout_logfile_maxbytes=0' \
    'stderr_logfile=/dev/stderr' \
    'stderr_logfile_maxbytes=0' \
    '' \
    '[program:logos]' \
    'command=python -m logos.main' \
    'autorestart=true' \
    'stdout_logfile=/dev/stdout' \
    'stdout_logfile_maxbytes=0' \
    'stderr_logfile=/dev/stderr' \
    'stderr_logfile_maxbytes=0' \
    > /etc/supervisor/conf.d/logos.conf

# Non-root user.  nginx writes its pid to /run/nginx.pid by default, which a
# non-root master cannot create — move it (and the temp paths) somewhere the
# logos user owns, or the master exits before it ever binds :5199.
RUN useradd --create-home --uid 1000 logos \
    && sed -i 's|^pid .*|pid /tmp/nginx.pid;|' /etc/nginx/nginx.conf \
    && mkdir -p /data/logos /var/log/nginx /var/lib/nginx/body /var/lib/nginx/proxy \
                /var/lib/nginx/fastcgi /var/lib/nginx/uwsgi /var/lib/nginx/scgi \
    && chown -R logos:logos /app /data/logos /var/log/nginx /var/lib/nginx /usr/share/nginx/html
USER logos

EXPOSE 5199

HEALTHCHECK --interval=20s --timeout=6s --retries=5 --start-period=20s \
    CMD curl -fsS http://127.0.0.1:9460/health || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/logos.conf"]
