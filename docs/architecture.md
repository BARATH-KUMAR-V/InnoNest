# InnoNest architecture

## Request flow

1. The browser talks to the FastAPI app under `/api/v1`. In single-server mode the same app serves the built React files.
2. Routers in `backend/app/api/v1` validate input with Pydantic, check the caller's role and call into `backend/app/services`.
3. Services own the business rules. They read and write through SQLAlchemy models and record every significant action in the audit trail.
4. The decision engine in `services/engine` is pure. It receives a snapshot and a policy, and returns financials, a risk score, rule results and an outcome. It does no input or output of its own.

## Application lifecycle

```
DRAFT -> SUBMITTED -> PROCESSING --+--> ACTION_REQUIRED -> DOCUMENTS_RECEIVED -> PROCESSING
                                   +--> VERIFICATION_PENDING -> PROCESSING
                                   +--> REFERRED -> APPROVED | REJECTED   (manual review)
                                   +--> APPROVED | REJECTED               (engine decision)
ACTION_REQUIRED -> EXPIRED                                                (no response in time)
any open state  -> WITHDRAWN                                              (applicant action)
```

`workflow.py` is the single place that changes status. The pipeline runs in order: completeness check, document reading, KYC, AML, fraud indicators, income assessment, property assessment, financial engine, scorecard, policy rules, decision. If the completeness check finds anything missing, unreadable, wrong or in conflict, the pipeline stops and holds the application in `ACTION_REQUIRED` with one follow-up request per item. If a critical source is unavailable it stops and holds the application in `VERIFICATION_PENDING`. The engine never decides on partial evidence.

An upload, an edit to the application, a consent or a clarification each re-runs the completeness check. When nothing is open any more, the pipeline resumes from where it stopped.

## Follow-up

Each open item is a `DocumentRequest` row. Notifications go out on three channels: in-app (real), email and SMS (recorded with status `SIMULATED_NOT_SENT`). A background thread checks every few minutes, sending the next reminder when the configured interval has passed and expiring the application when the deadline passes. `POST /follow-up/run` runs the same check on demand and can advance the clock for demonstration.

## Decisions

A decision stores the input snapshot, the policy version it used, the rule results, the reason codes, a plain-language explanation generated from those results, and a SHA-256 result hash. Replaying recomputes the result from the stored snapshot and policy and compares hashes. Manual review adds a second decision of kind `MANUAL` and does not edit the first.

## Policies

Three illustrative policies (Balanced, Conservative, Flexible) are stored as versioned JSON. Publishing a change archives the active row and inserts a new version. Old decisions keep pointing at the version they used.

## Providers

`backend/app/providers` has one adapter per source behind a shared envelope. Modes are `MOCK`, `SANDBOX` and `LIVE_PARTNER`. The live mode returns `NOT_CONFIGURED`. The service layer records every call, with its consent reference and response hash, so the evidence graph can link a verification result back to the call that produced it.

## Audit

Every audit row stores the hash of the previous row and its own hash over the previous hash and its content. `GET /audit/verify` walks the chain and reports the first broken link.

## Frontend

`src/pages/portal` holds the applicant screens and `src/pages/workspace` the lender screens. Server state goes through TanStack Query. Forms use React Hook Form with Zod. The base components in `src/components/ui` follow the shadcn/ui pattern on Radix primitives. Brand constants are in `src/lib/brand.ts` and the logo is in `src/components/Logo.tsx` and `public/`.
