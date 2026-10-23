# PayRail

PayRail is an early-stage stablecoin payment infrastructure project. The current implementation includes a development merchant API-key flow, merchant-scoped payment intents, a Solidity Payment Router, local mock-token Foundry tests, Base Sepolia receipt verification, a hosted injected-wallet checkout, and an ARQ worker that periodically reconciles submitted payments and canonical block hashes. Checkout requires a router deployed and configured by the operator. No contract has been deployed and no blockchain transaction has been submitted from this repository. Reorg checks are periodic and cannot reverse merchant fulfillment; this is not production-ready for funds.

## Repository layout

- `apps/web` — Next.js, TypeScript, and Tailwind CSS starter
- `apps/api` — FastAPI service with SQLAlchemy/Alembic dependencies
- `apps/worker` — ARQ payment confirmation and reorg reconciliation worker
- `contracts` — Foundry Payment Router and local mock-token tests
- `packages/sdk` — future TypeScript SDK package
- `docs` — architecture, setup, API, deployment, security, and status
- `tests` — reserved for integration and end-to-end suites
- `infrastructure` — infrastructure notes; local Compose lives at the root

## Quick start

1. Copy `.env.example` to `.env` for local development. Its PostgreSQL/Redis URLs match the host ports in Compose; the API and web ports are 8001 and 3001.
2. Start PostgreSQL and Redis with `docker compose up -d`.
3. Install JavaScript dependencies with `pnpm install`.
4. Install Python dependencies using the commands in [Local setup](docs/setup.md).
5. Start the web app with `pnpm dev:web`, the API with `uvicorn app.main:app --reload` from `apps/api`, or the worker with `arq payrail_worker.worker.WorkerSettings` from `apps/worker`.

The worker command is `arq payrail_worker.worker.WorkerSettings` from `apps/worker`; see [docs/setup.md](docs/setup.md) for polling configuration and [docs/api.md](docs/api.md) for state transitions. See [contracts/README.md](contracts/README.md) for contract test commands and [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) for phased work. `NEXT_PUBLIC_API_URL` is embedded into the web app at build time; set it to the public API HTTPS URL for a production build. Payment verification requires a configured Base Sepolia RPC endpoint and router/token addresses. Checkout requires a router deployment matching the source; this repository does not deploy it. This demo has not received an independent security review and is not ready to process production funds.

For hosting, see [docs/deployment.md](docs/deployment.md). Vercel can host the Next.js web app; the API, worker, PostgreSQL, and Redis require separate hosting. Production deployment and contract deployment have not been performed.
