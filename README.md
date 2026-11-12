# InnoNest

**Smart and trustworthy home lending.**
*Smarter Lending. Faster Homeownership.*

InnoNest is a working prototype of an underwriting platform for **Home Loan** and **Loan Against Property (LAP)** applications. It was built for the IIT Bombay E-Cell i-HACK, Hero Housing Fintech Challenge, problem statement 2.

An applicant submits one application. InnoNest reads the documents, runs KYC, AML and fraud checks, works out affordability and property cover, scores risk, and produces an APPROVE, REJECT or REFER decision with reasons. If something is missing, the application is never rejected for that. It moves to `ACTION_REQUIRED`, the applicant is told exactly what to send, reminders go out on a schedule, and underwriting resumes by itself when the answer arrives.

Everything in this repository runs locally. It needs no paid API and no API key.

> **Read this first.** This is a prototype. Every external data source (PAN, CKYC, Aadhaar offline verification, DigiLocker, credit bureau, Account Aggregator, GST, ITR, CERSAI, property registration, sanctions screening) is a **MOCK** or **SANDBOX** adapter reading local synthetic data. Nothing is connected to a live partner. The three lender policies are illustrative and are not any real lender's rules. All people, PANs and documents in the demo are synthetic.

## Contents

1. [Features](#features)
2. [Technology](#technology)
3. [Folder structure](#folder-structure)
4. [Prerequisites](#prerequisites)
5. [Installation and running locally](#installation-and-running-locally)
6. [Environment configuration](#environment-configuration)
7. [Database setup](#database-setup)
8. [Docker](#docker)
9. [Demo credentials](#demo-credentials)
10. [Sample scenarios](#sample-scenarios)
11. [API documentation](#api-documentation)
12. [Tests](#tests)
13. [How the integrations are mocked](#how-the-integrations-are-mocked)
14. [Design decisions](#design-decisions)
15. [Known limitations](#known-limitations)

## Features

**Applicant portal**
- Register, sign in, and start a Home Loan or LAP application in four steps with inline validation.
- Application list with search, status filter and pagination.
- Application page with a progress bar, a checklist of what is still needed, document upload and replacement, and a decision summary.
- Clarification dialog for information conflicts, for example a name that differs between two documents.
- In-app notifications. Email and SMS messages are recorded but clearly marked as simulated and are not sent.
- EMI and eligibility calculator.

**Lender workspace** (underwriter, policy administrator, auditor)
- Dashboard with figures and charts computed from the database.
- Application register with search, filters, sorting, pagination and CSV export.
- Application view with tabs: Summary, Verification (KYC, AML, fraud, provider calls), Financial, Risk, Property, Decision, Evidence graph, Audit.
- Decision tab: reasons, every rule result, decision replay, side by side comparison across the three policies, and manual review of referred cases.
- Policy configuration with versioning. Each change creates a new version with a reason.
- Follow-up monitoring: reminder schedule, expiry, a manual sweep with an advance-the-clock control to show the schedule without waiting days.
- Integration status page with a simulated outage switch.
- Audit history with a hash chain you can verify, and a CSV export.

**Engine and workflow**
- Seventeen-step lifecycle from draft to decision, with the statuses `DRAFT`, `SUBMITTED`, `PROCESSING`, `ACTION_REQUIRED`, `DOCUMENTS_RECEIVED`, `VERIFICATION_PENDING`, `REFERRED`, `APPROVED`, `REJECTED`, `EXPIRED`, `WITHDRAWN`.
- Document reading with PyMuPDF text extraction and a Tesseract and OpenCV path for scans (denoise, threshold, deskew).
- Integrity indicators on documents (editing software in the metadata, modified after creation, arithmetic that does not add up, mixed typefaces, OCR against text mismatch). These are indicators for a person to review. They are never described as proof of forgery or of authenticity.
- Financial engine: EMI, FOIR and LTV from published formulas, with the lowest documented income used when sources disagree.
- Property assessment: seller and owner match, valuation against declared value, encumbrance, property type. Text extraction is never treated as legal title. Legal opinion and technical inspection are shown as not checked until a report is read.
- Scorecard of six weighted factors with a stated maximum. It has not been validated on portfolio data, so it reports no probability of default and no accuracy figure.
- Decisions come only from the written rules. No language model makes or changes a decision.
- Evidence graph, decision replay with a result hash, and a hash-chained audit trail.

## Technology

| Area | Choice |
| --- | --- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui style components on Radix, React Router, TanStack Query, React Hook Form, Zod, Recharts, Lucide |
| Backend | Python, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Database | SQLite for local use. PostgreSQL through `DATABASE_URL` |
| Documents | PyMuPDF, Tesseract with pytesseract, OpenCV, pikepdf, ReportLab (to create synthetic specimens) |
| Auth | JWT bearer tokens, PBKDF2 password hashing, four roles |
| Tests | pytest |
| Deployment | Docker, Docker Compose |

## Folder structure

```
InnoNest/
├── backend/
│   ├── app/
│   │   ├── api/            routers (auth, applications, documents, follow-up, integrations, assessments, reports)
│   │   ├── core/           config, database, security, errors, migrations, branding
│   │   ├── models/         SQLAlchemy models
│   │   ├── schemas/        Pydantic request and response models
│   │   ├── providers/      mock and sandbox adapters for the external sources
│   │   ├── services/       workflow, extraction, checklist, verification, engine, policies, follow-up, reports
│   │   ├── demo/           demo scenarios and the scenario runner
│   │   └── scripts/        seed_demo.py, generate_samples.py
│   ├── alembic/            migration scripts
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── requirements-postgres.txt
│   └── Dockerfile
├── frontend/               React application (src/pages/portal, src/pages/workspace, src/components)
├── tests/                  pytest suite
├── data/                   synthetic sandbox registry, synthetic watchlist, sample documents
├── uploads/                uploaded files at run time
├── docs/                   architecture and decision notes
├── docker-compose.yml
├── .env.example
└── README.md
```

## Prerequisites

- Python 3.11 or newer (developed and tested on 3.13)
- Node.js 18 or newer and npm (developed and tested on Node 20)
- Tesseract OCR installed on the system, for scanned documents. On Debian or Ubuntu: `sudo apt install tesseract-ocr`. On macOS: `brew install tesseract`. Without it everything still runs, but image uploads that need OCR cannot be read.
- Docker and Docker Compose, only if you want the container route

## Installation and running locally

From the `InnoNest` folder.

**1. Backend**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload --port 8000
```

On start-up the app applies the database migrations, loads the three illustrative policies and creates the demo users. The API is at `http://localhost:8000/api/v1` and the interactive docs at `http://localhost:8000/docs`.

**2. Frontend, development mode**

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the backend on port 8000.

**3. Frontend, single-server mode**

```bash
cd frontend
npm install
npm run build
```

With `frontend/dist` present, the backend serves the built app itself. Open `http://localhost:8000` and no second server is needed.

**4. Load the demo applications (optional)**

With the backend running:

```bash
cd backend
python3 -m app.scripts.seed_demo
```

This creates the eight scenarios listed below as the demo applicant, and runs each through the real API. It does nothing if applications already exist.

**5. Regenerate the sample documents (optional)**

```bash
cd backend
python3 -m app.scripts.generate_samples
```

This writes synthetic specimen PDFs for every scenario into `data/samples/`, so you can upload them by hand through the UI. The `incomplete_application` folder has a `to_upload_later` folder with the two documents that scenario leaves out.

## Environment configuration

Copy `.env.example` to `.env` in the project root. Every value has a safe local default, so the file is optional for a first run.

| Variable | Meaning | Default |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy URL | SQLite file in `data/` |
| `UPLOAD_DIR` | Where uploaded files are stored | `uploads/` |
| `JWT_SECRET` | Signing key for tokens. **Change it for any shared deployment** | a placeholder |
| `TOKEN_EXPIRE_MINUTES` | Token lifetime | 480 |
| `MAX_UPLOAD_MB` | Largest accepted upload | 8 |
| `REMINDER_INTERVALS_HOURS` | Hours between reminders | `[24,72,120]` |
| `EXPIRY_DAYS` | Days before an unanswered request expires the application | 14 |
| `ENABLE_SCHEDULER` | Run the background follow-up job | `true` |
| `SCHEDULER_INTERVAL_SECONDS` | How often that job checks | 300 |
| `CORS_ORIGINS` | Allowed browser origins | localhost 5173 and 8000 |
| `SEED_DEMO_DATA` | Create the demo users on start-up | `true` |
| `PROVIDER_MODES` | JSON map choosing `MOCK` or `SANDBOX` per source, for example `{"bureau":"MOCK"}` | `{}` |

The reminder schedule and expiry can also be changed from the Follow-up monitoring page. That setting is stored in the database and takes precedence.

## Database setup

The app runs `alembic upgrade head` on every start, so a new database needs no manual step. To run migrations yourself:

```bash
cd backend
alembic upgrade head
```

Migration `0001` creates all fourteen tables. SQLite uses batch mode.

**PostgreSQL.** Install the driver and point `DATABASE_URL` at your database:

```bash
pip install -r requirements-postgres.txt
export DATABASE_URL="postgresql+psycopg://innonest:innonest-local-only@localhost:5432/innonest"
```

The PostgreSQL route was not run in this build. The test suite and the browser walkthrough ran on SQLite only.

## Docker

```bash
docker compose up --build
```

This builds the frontend, installs Tesseract and the Python packages in one image, and serves everything on `http://localhost:8000`. Data and uploads live in named volumes.

To run with PostgreSQL:

```bash
docker compose --profile postgres up --build
```

and set `DATABASE_URL=postgresql+psycopg://innonest:innonest-local-only@db:5432/innonest` in `.env` first.

The Docker files were written and the compose file passes `docker compose config`, but the image was **not built or run** because the workspace this was prepared in has no Docker daemon. Treat the Docker route as untested.

## Demo credentials

These are local demonstration accounts with synthetic data. Change or remove them before any real deployment.

| Role | Email | Password |
| --- | --- | --- |
| Applicant | `applicant@example.com` | `Applicant@123` |
| Applicant (second) | `applicant2@example.com` | `Applicant@123` |
| Underwriter | `underwriter@example.com` | `Underwriter@123` |
| Policy administrator | `policy@example.com` | `PolicyAdmin@123` |
| Auditor | `auditor@example.com` | `Auditor@123` |

What each role can do: applicants see and edit only their own applications. Underwriters review referrals, disposition flagged checks, correct extracted values, re-run and retry. Policy administrators publish policy versions. Auditors have read access and the audit export.

## Sample scenarios

`python3 -m app.scripts.seed_demo` creates these. Each shows a different path through the system.

| Scenario | What happens | Result |
| --- | --- | --- |
| `clean_home_loan` | Complete documents, within every limit | APPROVED |
| `high_foir` | EMI too heavy for income under the Balanced policy. The Flexible policy would approve it, which the policy comparison shows | REJECTED |
| `tampered_slip` | Salary slip edited after creation, with figures that do not add up and disagree with the bank statement | REFERRED |
| `aml_potential_match` | Name resembles an entry on the synthetic watchlist | REFERRED |
| `lap_encumbered` | Property already carries a charge in the security interest search | REFERRED |
| `weak_credit` | Bureau score below the policy floor | REJECTED |
| `clean_lap` | Complete Loan Against Property application | APPROVED |
| `incomplete_application` | Submitted without a salary slip and bank statement | ACTION_REQUIRED |

**To see the follow-up loop:** sign in as the demo applicant, open the `incomplete_application` case, and upload the two files from `data/samples/incomplete_application/to_upload_later/`. The application resumes and is approved without anything else being clicked.

**To see reminders and expiry:** sign in as the underwriter, open Follow-up monitoring and run the check with the clock advanced by 24, then 96, then 216 and finally 720 hours. Each figure is counted from the real current time. The first three runs send reminders one, two and three, and the last one expires the application. (This sequence was run against the API and gave exactly those results.)

**To see a manual review:** as the underwriter open `tampered_slip` or `aml_potential_match`, go to Decision, record a reasoned APPROVE or REJECT.

**To see a simulated outage:** as the underwriter open Integrations, take the credit bureau down, submit a new application, and note that it waits in `VERIFICATION_PENDING`. Restore the source and use Retry verification.

## API documentation

- Interactive docs (Swagger UI): `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`
- Health check: `http://localhost:8000/api/health`

Errors always use one shape: `{"error": {"code", "message", "details"}}`.

## Tests

```bash
python3 -m pytest tests
```

Run from the project root. The suite uses a temporary database and upload folder, so it never touches your own data. Frontend checks:

```bash
cd frontend
npm run build
```

`npm run build` runs the TypeScript compiler and then the production build.

What the backend tests cover: EMI, FOIR and LTV against hand-calculated values; invalid inputs; application creation and ownership; document upload including duplicates and bad files; missing-evidence detection; the `ACTION_REQUIRED` flow, notifications, resubmission and automatic resumption; clarification of conflicts; KYC and AML referral; fraud indicators; policy evaluation across the three policies; APPROVE, REJECT and REFER outcomes; manual review; decision replay; the audit hash chain; CSV exports; and authentication and role permissions.

## How the integrations are mocked

Every source implements one adapter interface and returns one response envelope that carries the provider, the **mode**, a response status, a consent reference, a source reference and a verification result.

- `MOCK`: a deterministic response generated locally.
- `SANDBOX`: a response replayed from `data/sandbox_registry.json`, which is keyed by PAN and shaped like a partner sandbox.
- `LIVE_PARTNER`: calls a live partner. No credentials exist in this build, so it returns `NOT_CONFIGURED` and never fakes a success.

Each adapter records the production route it would use (for example the licensed Account Aggregator framework for bank statements, or an authorised partner for Aadhaar offline verification). The sanctions screen reads `data/synthetic_watchlist.csv`, which is an invented list and not a real sanctions list. The Integrations page labels every source with its mode, and a simulated outage on a critical source holds the application in `VERIFICATION_PENDING` instead of deciding on partial evidence.

## Design decisions

- **Missing information is never a rejection.** Anything absent, unreadable, the wrong document type or in conflict creates a follow-up request and moves the application to `ACTION_REQUIRED`.
- **Decisions are deterministic.** The engine is a pure function of a stored snapshot and a stored policy version. Replaying a decision recomputes the same result and the same hash.
- **Policies are data.** They are versioned JSON in the database, so a change never rewrites history.
- **Honest labelling.** Simulated email and SMS, mock providers, indicator-only fraud findings and the unvalidated scorecard are all labelled as such in the interface.

More detail is in [docs/architecture.md](docs/architecture.md).

## Known limitations

- No live integration exists. Every provider response is synthetic.
- The three policies are illustrative and are not any real lender's credit policy.
- The scorecard weights are illustrative and have not been validated on real outcomes. It gives no probability of default.
- Document integrity checks are indicators. A clean result does not prove a document is genuine, and a flag does not prove it is forged. OCR and hashing do not establish legal title, and legal opinion and technical inspection are left as not checked.
- OCR quality depends on the scan. It was tested on synthetic scans with mild skew and noise, not on real-world photographs.
- Email and SMS are simulated. The SMTP settings exist but no mail is sent.
- Extraction expects documents laid out as `Label: value` lines, as the synthetic specimens are. Real issuer formats would need their own parsers.
- Language support is English only in the interface.
- Passwords use PBKDF2 and tokens are JWT bearer tokens, but there is no rate limiting, multi-factor sign-in, token revocation or password reset. Do not expose this to the internet as it stands.
- Uploaded files are stored on local disk without encryption or malware scanning.
- Only SQLite was exercised. PostgreSQL and the Docker image are untested here.
- The dashboard average decision time is only computed on SQLite.
- The frontend has no automated component tests. It was checked by the production build and a scripted browser walkthrough.
