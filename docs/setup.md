# Local setup

## Prerequisites

- Node.js 20 or newer and pnpm 9
- Python 3.11 or newer
- Docker Engine with the Compose plugin
- Foundry is required to compile and test the Payment Router

## Start local dependencies

Copy `.env.example` to `.env`, then run `docker compose up -d`. The example credentials are for local development only. Never deploy them or commit a real `.env` file. Export the values before starting the API with `set -a; source .env; set +a`; the app defaults to a local SQLite file when `DATABASE_URL` is unset.

## Install and start services

Run `pnpm install` at the repository root. Create a Python virtual environment with `python3 -m venv .venv`, activate it with `source .venv/bin/activate`, then install the API and worker dependencies with `pip install -e './apps/api[dev]' -e apps/worker`.

Run the API migration from `apps/api` with `alembic upgrade head`, then start it with `uvicorn app.main:app --reload`. Start the worker from `apps/worker` with `arq payrail_worker.worker.WorkerSettings`. `PAYMENT_RECONCILE_BATCH_SIZE` is configurable from 1 to 5 (default 5), matching the worker's maximum RPC concurrency. Set `PAYMENT_RECONCILE_INTERVAL_SECONDS` (5–3600, default 15) to configure the polling interval, and `PAYMENT_MIN_CONFIRMATIONS` to configure the confirmation threshold. Receipt confirmations below threshold are checked at the polling interval; transient/missing-receipt retries back off to a five-minute maximum. `RPC_TIMEOUT_SECONDS` bounds RPC calls. The worker writes Redis heartbeat and per-batch counter keys `payrail:worker:heartbeat` and `payrail:worker:metrics` for health/operations. Start the web app with `pnpm dev:web`.

For direct local commands, export values from the root `.env` first so the API and worker receive the same database, Redis, and RPC settings. Alembic revision `0004_payment_reconciliation` adds due-time scheduling, leases, attempt counters, and check/reorg timestamps without replacing existing tables or records. Compose also checks the worker's Redis heartbeat; no public endpoint can trigger an arbitrary reconciliation scan.

For a local API smoke test, register a development merchant with `POST /v1/merchants` and use the returned API key as a Bearer token. The API accepts integer USDC base units. To enable request-driven Base Sepolia transaction verification and checkout, configure the RPC endpoint, deployed router address, and USDC address shown in `.env.example`. The repository does not deploy contracts or submit blockchain transactions as part of setup.

Set `CORS_ORIGINS` to a comma-separated list of exact browser origins when hosting web and API separately. Do not use `*` for a deployed API.

The API's `/health` route reports process health; `/ready` checks the configured database connection only. Redis and blockchain readiness are not checked by the API.
