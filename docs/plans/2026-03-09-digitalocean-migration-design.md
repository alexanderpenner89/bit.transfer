# Migration: Raspberry Pi → DigitalOcean Droplet

## Decision
Replace Raspberry Pi self-hosted deployment with a DigitalOcean Droplet (s-1vcpu-2gb, fra1).

## Architecture

```
Cloudflare (DNS + SSL, Proxy mode)
    │
    ▼
alexanderpenner.de → 209.38.209.103 (Droplet fra1)
    │
    Nginx (port 80, reverse proxy)
    ├── /              → Ghost CMS (2368)
    ├── /blog          → Ghost CMS (2368, alias)
    └── /devtools/     → FastAPI backend (8000)
```

## Services (docker-compose.prod.yml)
- **nginx** — Alpine, reverse proxy, port 80
- **devtools** — FastAPI backend (Dockerfile.devtools)
- **ghost** — Ghost 5 Alpine, production mode
- **mysql** — MySQL 8.0 for Ghost

## Deployment
- GitHub Actions on push to `main`
- SSH into Droplet via `appleboy/ssh-action`
- `docker compose -f docker-compose.prod.yml up -d --build`

## Files changed
- Added: `docker-compose.prod.yml`, `nginx/nginx.conf`
- Modified: `.github/workflows/deploy.yml`
- Removed: `docker-compose.pi.yml`

## Manual setup required
1. SSH key on Droplet + GitHub secret `DO_SSH_PRIVATE_KEY`
2. Cloudflare A-record: `alexanderpenner.de` → `209.38.209.103`
3. `.env` file at `/root/.env.bit-transfer` on the Droplet
