# CropVision AI

Satellite-based crop disease detection and advisory platform for smallholder farmers,
agronomists, and agricultural cooperatives.

**Live demo credentials**
- Farmer: `farmer@cropvision.ai` / `farmer123`
- Agronomist: `agronomist@cropvision.ai` / `agro123`
- Admin: `admin@cropvision.ai` / `admin123`

---

## Architecture (30-second read)

```
              ┌─────────────────────┐
   n8n  ────► │  /api/n8n/ingest    │  (webhook)
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐    ┌──────────────────┐
              │  Async job queue    │───►│  vision.py       │  Claude Sonnet 4.5
              │  (BullMQ-shaped     │    │  (image ➝ JSON)  │  via emergent
              │   in-process)       │    └────────┬─────────┘  integrations
              └─────────────────────┘             │
                                                  ▼
                                        ┌───────────────────┐
                                        │  langgraph_agent  │  stateful graph:
                                        │  (multi-agent     │  diagnose →
                                        │   reasoning)      │  severity →
                                        └────────┬──────────┘  advisory →
                                                 │             confidence gate →
                                                 ▼             escalation
                                        ┌───────────────────┐
                                        │ MongoDB (detects, │
                                        │ alerts, audit)    │
                                        └────────┬──────────┘
                                                 ▼
              ┌─────────────────────┐    ┌───────────────────┐
              │ React + TS + Tailwind│◄───│  FastAPI /api/*   │
              │ (i18n, framer, chart)│    │  JWT+RBAC+audit   │
              └─────────────────────┘    └───────────────────┘
```

### Responsibility boundary — n8n vs LangGraph
| | n8n | LangGraph |
| --- | --- | --- |
| Job | orchestration + integrations | reasoning |
| Owns | Webhook trigger, retries, WhatsApp/SMS/email delivery, escalation notification, dead-letter | Disease refinement, severity scoring, bilingual advisory generation, confidence-gated retry loop, escalation decision |
| Files | `/app/n8n_workflow.json` | `/app/backend/langgraph_agent.py` |

The FastAPI backend implements the **same orchestration natively** (via `job_queue.py`) so
the full pipeline runs end-to-end in this environment even without a running n8n instance.

---

## Backend

- FastAPI + Motor + MongoDB (2dsphere geo index on `fields.location`)
- JWT access + refresh token rotation, RBAC (`farmer` / `agronomist` / `admin`)
- Rate limiting on auth endpoints
- Structured audit log for every state-changing action
- In-process async job queue with retry + dead-letter (drop-in replacement point for BullMQ)
- Observability: `/api/health`, `/api/metrics`, `/api/admin/pipeline`

Files:
- `server.py` — API layer + queue wiring
- `models.py` — Pydantic models
- `auth.py` — JWT + password hashing + RBAC
- `vision.py` — Claude Sonnet 4.5 vision inference (image ➝ JSON) + offline fallback
- `langgraph_agent.py` — stateful multi-agent reasoning graph
- `job_queue.py` — worker pool + retry/dead-letter
- `seed.py` — sample data

## Frontend

- React 19 + React Router 7 + Tailwind + framer-motion + recharts + sonner
- Bilingual (English / Hindi) via `react-i18next` — no hardcoded strings
- Auth flows fully wired to backend (login, refresh rotation, role-based nav)
- Skeleton/empty/error states everywhere
- `data-testid` on every interactive + informational element

Pages:
- `/` — Cinematic landing page (scroll-driven, spectral visuals)
- `/login`, `/signup` — Auth
- `/dashboard` — Live operational dashboard (fleet metrics, trend chart, field cards, alert feed)
- `/fields` — Field inventory
- `/fields/:id` — Detail: 14-day trend, detection history, LangGraph reasoning trace
- `/alerts` — Full alert feed
- `/queue` — Agronomist escalation queue (RBAC-gated)
- `/admin` — Pipeline health + audit trail (RBAC-gated)

---

## Run locally

```bash
# Backend
cd backend
pip install -r requirements.txt
python seed.py                     # seed users + fields + detections
uvicorn server:app --reload --port 8001

# Frontend
cd frontend
npm install
npm start
```

Environment variables

Backend local file: `backend/.env`
Backend example file: `backend/.env.example`

Required backend variables:
- `MONGO_URL` — MongoDB Atlas connection string
- `DB_NAME` — database name
- `JWT_SECRET` — strong signing secret for tokens
- `JWT_ALGORITHM` — `HS256`
- `ACCESS_TOKEN_MINUTES` — access token lifetime
- `REFRESH_TOKEN_DAYS` — refresh token lifetime
- `EMERGENT_LLM_KEY` — Emergent Claude Sonnet 4.5 / LangGraph API key
- `CORS_ORIGINS` — comma-separated frontend origin(s) for CORS

Frontend env sample: `frontend/.env.example`
- `REACT_APP_BACKEND_URL` — deployed backend base URL

## Production deployment

### GitHub
1. Initialize a git repository in the project root.
2. Add all files and commit the prepared project.
3. Push the repository to GitHub.

### Render backend
1. Create a new Python web service on Render and connect it to the GitHub repository.
2. Set the service root to the project repository and use the existing `render.yaml` file.
3. Build command: `pip install -r backend/requirements.txt`
4. Start command: `uvicorn backend.server:app --host 0.0.0.0 --port 10000`
5. Configure required environment variables from `backend/.env.example`.
6. Set `CORS_ORIGINS` to include your frontend origin, for example `https://<frontend-project>.vercel.app`.

### Vercel frontend
1. Create a new Vercel project from the same GitHub repository.
2. Use the `frontend` directory as the project root.
3. Build command: `npm run build`
4. Output directory: `build`
5. Set environment variable `REACT_APP_BACKEND_URL` to the Render backend URL.

### Connecting frontend and backend

- The frontend uses `REACT_APP_BACKEND_URL` to call the backend API.
- The backend uses `CORS_ORIGINS` to allow requests from the deployed frontend origin.

### Notes

- The backend `.env` file is ignored by git and should remain private.
- Use `backend/.env.example` and `frontend/.env.example` to copy values into your deployment environment.

## n8n workflow

Import `/app/n8n_workflow.json`. Required env vars in n8n:
```
CROPVISION_API           # e.g. https://your-host
CROPVISION_TOKEN         # bearer token for polling
CROPVISION_INGEST_KEY    # matches backend
TWILIO_SID, TWILIO_WHATSAPP_FROM
ALERT_FROM_EMAIL, AGRONOMIST_EMAIL, SLACK_ALERTS_WEBHOOK
```

## Placeholder / stub flags

| Item | Status |
| --- | --- |
| Claude Sonnet 4.5 vision inference | **Fully wired** (real API) with graceful offline fallback |
| LangGraph reasoning | **Fully wired** (real LLM calls, deterministic fallback prompts) |
| SMS / WhatsApp delivery | **Mocked** — alerts persisted to `alerts` collection with `channel:"dashboard"` and shown in real time. Wire Twilio via `n8n_workflow.json`. |
| n8n orchestration | **Exportable JSON provided** — same pipeline runs natively in FastAPI so app is end-to-end functional without n8n |
| Real satellite tile pipeline | **Sample-image based** — inference endpoint accepts any base64 crop image (JPEG/PNG/WEBP) |

All other flows (auth, RBAC, job queue, retry, audit, i18n, RBAC-gated routes, dashboards, historical trends) are fully implemented, not stubbed.
