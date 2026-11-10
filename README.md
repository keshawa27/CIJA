# CIJA — Client Intake Journey Automation

Prototype for Vela's Client Services team: an online intake form, automated triage,
automatic caseworker tasks, status notifications and a progress dashboard, behind
role-based access with an append-only audit trail.

> **Synthetic data only.** Never enter real client information into this prototype.

Design and rationale: [`imp_plan.md`](imp_plan.md).

## Run it

Needs Docker, Python 3.12+ and Node 22+.

```bash
# 1. Database (port 5433) and Mailpit, which catches all outgoing email
docker compose up -d

# 2. API
cd backend
python -m venv .venv
.venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # then set SECRET_KEY (the file says how)
alembic upgrade head
python -m scripts.seed            # 6 staff + 60 synthetic intakes
uvicorn app.main:app --reload     # http://127.0.0.1:8000/api/docs

# 3. Web app (new terminal)
cd frontend
npm install
npm run dev                       # http://localhost:3000
```

| What | Where |
|------|-------|
| Public intake form | http://localhost:3000 |
| Staff sign in | http://localhost:3000/login |
| Captured emails | http://localhost:8025 |
| API docs (dev only) | http://127.0.0.1:8000/api/docs |

### Demo accounts

Password for all: `demo-password-123` (override with `SEED_PASSWORD` when seeding).

| Role | Email | Sees |
|------|-------|------|
| Team lead | lead@example.com | Every case; can re-prioritise, reassign, skip a step |
| Caseworker | casey@example.com, jordan@example.com, riley@example.com | Only their own cases and tasks |
| Manager | manager@example.com | Dashboard numbers and reference codes, no names |
| Admin | admin@example.com | User accounts and the audit log, no case content |

Reset to a clean demo at any time: `python -m scripts.seed --reset` (wipes the database).

## Test it

```bash
cd backend  && pytest          # 125 tests, against a real Postgres database (cija_test)
cd backend  && ruff check .
cd frontend && npm run lint && npm run build
cd frontend && npm run e2e     # the whole demo in a browser; needs the stack above running
```

First time only for the browser test: `npx playwright install chromium`.

## Where things are

```
backend/app/
  journey.py    the stages and mandatory steps      <- edit to change the process
  triage.py     the triage rules                    <- edit to change priorities
  services.py   business rules; every change is audited here
  security.py   password hashing, sessions, role checks
  routers/      HTTP endpoints
backend/scripts/seed.py     synthetic data
backend/tests/              test_access.py holds the full role x endpoint matrix
frontend/app/(public)/      landing page, intake form, status lookup
frontend/app/(staff)/       dashboard, case page, tasks, admin
frontend/e2e/               end-to-end demo script
```

`journey.py` and `triage.py` are drafts until the sponsor confirms the real process
(see the open questions in `imp_plan.md` section 16).
