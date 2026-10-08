# CleanSpot (EVS)

A civic-reporting app: citizens snap a photo of illegal dumping, an AI checks
the photo, and municipal officers track the cleanup.

```
backend/   FastAPI + SQLAlchemy + SQLite (REST API, AI verification)
frontend/  React 18 + Vite (PWA, works offline)
```

## Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt          # CPU-only PyTorch build:
.venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m uvicorn app.main:app --port 8000
```

The API runs on `http://localhost:8000` (health check: `GET /health`).

### First-time configuration (backend/.env)

```bash
cd backend
cp .env.example .env
# generate a signing secret (REQUIRED unless DEBUG=1)
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
# CHANGE these demo passwords before any real use:
#   SEED_CITIZEN_PASSWORD / SEED_OFFICER_PASSWORD / SEED_ADMIN_PASSWORD
#   SEED_ZONE_OFFICER_PASSWORD (shared by officer_zone1..4)
```

The app **refuses to start** without a `SECRET_KEY` unless `DEBUG=1`
(local development only - never set DEBUG=1 in production).

### Demo accounts (created automatically at first start)

| Username | Role | Password (env variable) |
|---|---|---|
| `citizen` | citizen | `SEED_CITIZEN_PASSWORD` (default `citizen-demo-123`) |
| `officer` | officer (zone 1) | `SEED_OFFICER_PASSWORD` (default `officer-demo-123`) |
| `admin` | admin | `SEED_ADMIN_PASSWORD` (default `admin-demo-123`) |
| `officer_zone1` .. `officer_zone4` | officer (one per sample ward) | `SEED_ZONE_OFFICER_PASSWORD` (default `zone-officer-demo-123`) |

Citizens can also **register** their own account on the Login screen.
All passwords are stored as **bcrypt hashes** - never in plain text.

### Frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173 (dev, proxies /api to :8000)
npm run chrome         # production build + preview, opens in Chrome
```

### Tests

```bash
cd backend
.venv/bin/python -m pytest tests/ -q
```

## Authority login (separate from citizens)

Citizens use the normal **Login** tab (username + password, with registration).
Officers and admins use the separate **Authority Login** screen
(`/officer-login`, username + password). A citizen who tries that screen is
rejected - the role is enforced on the **server**, not just hidden buttons.

Login returns a **signed JWT** (HS256, `SECRET_KEY`) that expires after
`TOKEN_EXPIRE_HOURS` (default 12 h). Repeated wrong passwords are rate-limited
(5 attempts per minute per IP).

## After photo (cleanup confirmation from the authority)

When an officer resolves a complaint, they can attach an **after photo** and a
short note. The reporter sees both in *My Reports -> open complaint*:

- the officer's after photo is shown as "After photo from the authority"
- the note appears in the status timeline
- the reporter can still confirm or reopen afterwards

Late after photos are also allowed: open a resolved complaint in the queue and
use "Send after photo".

## Ward / zone filtering

Every complaint is stamped with a **zone id** the moment it is submitted
(`zone_for(lat, lng)` in `app/zones.py`). The zones come from
`backend/app/config/zones.json` - four **sample** rectangles that stand in for
real municipal wards (edit that file and restart the backend to change them;
anything outside every rectangle gets `unassigned`).

Who sees what:

| Role | Queue (`GET /municipal/complaints`) | Photos / assign / resolve | Stats |
|---|---|---|---|
| officer | **own zone only** (no `?zone=` accepted) | own zone only, 403 everywhere else | own zone only |
| admin | everything, or one zone via `?zone=zone1..4` / `?zone=unassigned` | any zone | everything, or `?zone=` |
| citizen | own reports only | own reports only | global view |

Other details:

- `GET /api/zones` (any logged-in user) returns the rectangles so the frontend
  can draw them on the maps and label reports with their ward name.
- Admins pick a zone in the dropdown on the Authority screen; officers just see
  their zone's name in the header. The queue map draws the ward rectangle plus
  one pin per complaint.
- Reports are zoned **geometrically at submission time** - a complaint never
  changes zone when a user or zone boundary is edited later.

## Security

- **Roles**: `citizen`, `officer`, `admin` - enforced on the server with
  `require_role(...)` dependencies. Citizens read only their **own**
  complaints and photos (403 for anything else).
- **Passwords**: bcrypt-hashed (`password_hash` column); seeded account
  passwords come from the environment - **change them before any real use**.
- **Tokens**: signed JWTs with expiry; the app refuses to start without a
  real `SECRET_KEY` outside `DEBUG=1`.
- **Photos are not public**: the `/uploads` static mount is gone. Photos are
  served only through `GET /api/photos/{complaint_id}/{kind}` (`report`,
  `after`, `cleanup`) and `GET /api/photos/event/{event_id}` with a valid
  token. Files use random UUID names.
- **Upload validation**: only JPEG/PNG/WebP accepted (checked on the real
  content with Pillow), max size `MAX_UPLOAD_SIZE_MB` (8 MB), max dimension
  `MAX_IMAGE_DIMENSION` (4096 px, downscaled). Every upload is **re-encoded**
  with Pillow, which strips all metadata including EXIF GPS.
- **Web**: CORS restricted to `CORS_ALLOW_ORIGINS`; security headers
  (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`); generic
  login error messages; no stack traces to clients; login rate limit.
- **Privacy / retention**: `DELETE /admin/complaints/{id}` (admin) or
  `backend/scripts/purge_complaint.py <id>` erase a complaint, its status
  events and its photo files. Suggested retention: purge resolved/confirmed
  complaints older than ~90 days from a weekly cron job.

### Hosting limitations (read this before deploying)

- **HTTPS is required** in production - bearer tokens in localStorage are
  readable by any script on the page if the connection is not TLS.
- SQLite and local-disk uploads are fine for a demo/college project, but a
  real deployment needs a managed database (e.g. PostgreSQL) and managed file
  storage (e.g. S3) - the local disk is not shared across instances and has
  no backups.
- Set `DEBUG=0`, a long random `SECRET_KEY`, and change every seeded password.

## The AI image classifier

Every uploaded photo is checked by a trained **MobileNetV2** model that is
exported as TorchScript:

| | |
|---|---|
| File | `backend/models/garbage_classifier.pt` |
| Classes | index `0` = `not_garbage`, index `1` = `garbage` |
| Input | 224x224 RGB, ImageNet normalization |
| Output | softmax over the 2 logits; the class-1 probability is stored as `ai_confidence` |

The model is loaded once (on the first submission) and cached. Install the
**CPU build** — no GPU is needed:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### Replacing the model file

1. Export the new model with `torch.jit.trace(...)` or `torch.jit.script(...)`
   (a state dict will **not** work - it must be a TorchScript file).
2. Save it as `backend/models/garbage_classifier.pt`, or put it anywhere and
   point `MODEL_PATH` at it:

```bash
# in backend/.env
MODEL_PATH=models/garbage_classifier.pt
```

3. Restart the backend. The model is only read at startup, never modified.

If the file is missing or broken, the backend logs the error and every photo
falls back to `needs_review` with confidence `0.0` — submissions keep working.

### Changing the decision thresholds

Two environment variables control what happens to a complaint:

| Variable | Default | Meaning |
|---|---|---|
| `AUTO_ACCEPT` | `0.80` | `confidence >= AUTO_ACCEPT` -> **accepted** (auto) |
| `REVIEW_BELOW` | `0.50` | `confidence >= REVIEW_BELOW` -> **needs_review** |
| | | `confidence < REVIEW_BELOW` -> **needs_review_low_confidence** |

```bash
# in backend/.env  (example: be stricter before auto-accepting)
AUTO_ACCEPT=0.90
REVIEW_BELOW=0.60
```

A complaint is **never rejected automatically** - low confidence still creates
the complaint and flags it for human review. If the two values are set to
something invalid (`REVIEW_BELOW >= AUTO_ACCEPT`), the older
`AI_CONFIDENCE_THRESHOLD` (default `0.7`) is used as a fallback.

Decisions are stored per complaint in `ai_decision` and shown as a badge
(Accepted / Needs review) in the Authority view.

### Limitation

> The model judges **what a photo shows** (garbage vs. not garbage). It does
> not judge **whether the photo is genuine** — a photo of a screen, a
> printout, or someone else's picture would pass the AI check. Duplicate
> detection and human review still apply.

## API overview

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /api/auth/register` | public | create a citizen account |
| `POST /api/auth/login` | public | username + password -> signed token |
| `POST /api/citizen/submit` | any user | upload a report (photo + location) |
| `GET /api/citizen/complaints` | any user | my own reports |
| `GET /api/photos/{id}/{kind}` | any user | authenticated photo (`report`/`after`/`cleanup`) |
| `GET /api/stats` | any user | dashboard statistics (officer: own zone, admin: `?zone=`) |
| `GET /api/zones` | any user | sample ward rectangles (map + labels) |
| `GET /municipal/complaints` | officer/admin | cleanup queue (officer: own zone, admin: `?zone=`) |
| `POST /municipal/complaints/{id}/assign` | officer/admin | assign a complaint |
| `POST /municipal/complaints/{id}/resolve` | officer/admin | resolve + optional after photo & note |
| `DELETE /admin/complaints/{id}` | admin | erase complaint + photos (retention) |

Status flow: `Reported -> Assigned -> Resolved -> Confirmed` (a citizen can
`reopen` a resolved complaint; the AI can set `Needs review` at submission).

## Complete workflow

1. **Setup** - copy `.env.example` to `.env`, set `SECRET_KEY` and the four
   seed passwords, start the backend (uvicorn) and the frontend (`npm run dev`).
2. **Citizen registers / logs in** on the Login tab, snaps a photo on Home,
   drags the pin if needed, picks a waste type and submits.
3. **AI check** - the photo goes through the TorchScript classifier. High
   confidence -> status *Reported*; otherwise *Needs review* for the officers.
   Location duplicates (within 30 m) are linked instead of duplicated.
4. **Officer logs in** on the Authority tab, sees the queue for **their ward**
   only (with the ward rectangle drawn on the map), opens a complaint, assigns
   it, then resolves it - optionally attaching an **after photo** and a note
   for the reporter. An officer in another ward gets a 403 on the same id.
5. **Reporter follows along** in My Reports: status stepper, timeline, the
   officer's after photo, then confirms cleanup (with their own after photo)
   or reopens if it was not done. Each card shows the ward chip.
6. **Admin** can log in on the Authority tab too: sees every ward, picks a ward
   (or *Unassigned*) from the zone dropdown, and can erase old complaints via
   `DELETE /admin/complaints/{id}` or the purge script.
7. **Dashboard** (bottom tab) shows monthly statistics, hotspots and categories
   for the officer's own ward; the admin sees everything or the selected ward.
