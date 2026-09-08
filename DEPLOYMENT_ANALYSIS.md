# Deployment Platform Analysis — AirIndex India

## Project Stack Summary

| Component | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, uvicorn |
| Frontend | React 19 + TypeScript + Vite + Tailwind |
| Database | PostgreSQL 16 |
| Container | Docker + docker-compose.yml |
| CI/CD | GitHub Actions (already configured) |
| Auth | JWT + RBAC (PyJWT) |
| Migrations | Alembic |
| Scheduler | APScheduler (cron) |

---

## Free Tier Comparison

### 1. Render (⭐ RECOMMENDED)
- **Frontend**: Static hosting — free, unlimited
- **Backend**: Web Service — 15 CPU-hours/month, 512MB RAM
- **Database**: PostgreSQL — free (5GB storage, 3 connections)
- **Docker**: Native `docker-compose.yml` support via `render.yaml`
- **Pros**: All-in-one, free PostgreSQL, native Docker, GitHub sync
- **Cons**: 15hr/month CPU limit (enough for demo, not production)
- **Best fit**: Full-stack deploy in one platform

### 2. Vercel (Frontend) + Supabase (Backend + DB)
- **Frontend**: Vercel — free, unlimited build minutes
- **Backend**: Supabase Edge Functions — free tier available
- **Database**: Supabase PostgreSQL — free (500MB, 50K rows, 2GB file storage)
- **Auth**: Supabase Auth built-in (replaces JWT setup)
- **Pros**: Best DX for React apps, excellent free tier for frontend
- **Cons**: Backend rewrite needed for Edge Functions, DB schema migration needed
- **Best fit**: React-heavy apps prioritizing frontend performance

### 3. Fly.io
- **Frontend**: Static + container — 3 shared VMs (256MB each)
- **Backend**: Container VM — same shared pool
- **Database**: Managed PostgreSQL — **not free** ($15/mo minimum)
- **Docker**: Native Dockerfile support
- **Pros**: Global edge deployment, fast cold starts
- **Cons**: No free DB, very limited free resources
- **Best fit**: Docker-native apps that can bring their own DB

### 4. Railway
- **Frontend**: Static — not available on free tier
- **Backend**: Container — $5/month credit
- **Database**: PostgreSQL — $5/month credit
- **Docker**: Native Dockerfile support
- **Pros**: Simple `docker-compose` integration, easy setup
- **Cons**: No free tier (only trial credit), frontend not included
- **Best fit**: Quick prototype with minimal config

### 5. Google Cloud Run (Free Tier)
- **Backend**: Cloud Run — 180K vCPU-seconds/month, 36GB RAM-months
- **Database**: Cloud SQL — no free tier (Cloud SQL has paid-only tier)
- **Frontend**: Firebase Hosting — free, unlimited bandwidth
- **Pros**: Generous compute free tier, reliable
- **Cons**: No free DB, complex setup, requires GCP account
- **Best fit**: Developers already in the Google ecosystem

---

## Recommendation

**Primary: Render** — the only platform offering a genuinely free PostgreSQL database, free static hosting, and free web services all in one place. The existing `deployment/docker-compose.yml` maps almost directly to Render's `render.yaml` configuration. The project is already on GitHub with CI workflows, making the GitHub-to-Render pipeline seamless.

**Migration steps for Render**:
1. Create `render.yaml` referencing the existing `docker-compose.yml`
2. Connect GitHub repo (`Barathraj009/AirIndex`)
3. Set environment variables from `.env.example`
4. Deploy — Render builds Docker images and runs the stack

**Alternative split approach** (if Render's 15hr limit is insufficient):
- Vercel (frontend) + Supabase (PostgreSQL + Auth) + Railway ($5/mo credit for backend)
- This gives better scaling but adds integration complexity

---

## Environment Variables Needed for Deployment

| Variable | Render Value | Notes |
|---|---|---|
| `DATABASE_URL` | Auto-provisioned by Render | Replace with Render's PostgreSQL URL |
| `JWT_SECRET_KEY` | Generate securely | **Must rotate before deployment** |
| `SEED_ADMIN_EMAIL` | Production admin email | **Change from demo creds** |
| `SEED_ADMIN_PASSWORD` | Production admin password | **Change from demo creds** |
| `ENVIRONMENT` | `production` | |
| `CORS_ALLOWED_ORIGINS` | Vercel/Render frontend URL | |
| `VITE_API_BASE_URL` | Backend API URL | |
| `ALERT_SMTP_HOST` | SMTP server | For surge alerts |
| `ALERT_WEBHOOK_URL` | Webhook URL | For surge alerts |

---

## Notes

- The existing `deployment/docker-compose.yml` uses a single `backend` volume mount (`../backend:/app/backend`) — Render requires rebuilding on each deploy or using a separate volume mount strategy.
- The `Dockerfile.backend` runs `alembic upgrade head && seed_database.py` on startup — this is compatible with Render's build pipeline.
- Playwright is **not** baked into the Docker image (intentionally excluded per the Dockerfile comments), so scraping adapters won't work on Render without additional setup.
- The project's `Dockerfile.backend` is optimized for the demo/compose-verify flow; for production on Render, consider baking the frontend build into the backend image or using separate services.
