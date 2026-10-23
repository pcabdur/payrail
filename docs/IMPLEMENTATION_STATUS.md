# Implementation status

This repository is a development scaffold. A checked item means the repository setup exists, not that payment functionality is implemented.

## Phase 0 — Workspace foundation

- [x] Establish monorepo directories and workspace configuration.
- [x] Add environment example and ignore rules for secrets and generated files.
- [x] Add formatting configuration and root README.
- [x] Add local PostgreSQL and Redis Compose configuration.
- [x] Add CI checks and a pnpm dependency lockfile.
- [ ] Add a pinned Python dependency lockfile.
- [x] Add a Foundry test CI job with a pinned toolchain and OpenZeppelin version.

## Phase 1 — Service foundations

- [x] Create Next.js, TypeScript, and Tailwind web starter.
- [x] Create FastAPI application and health route.
- [x] Add SQLAlchemy, Alembic, and PostgreSQL driver dependencies and migration scaffolding.
- [x] Create ARQ worker entry point and Redis settings.
- [x] Add Foundry configuration and contract placeholders.
- [x] Add future TypeScript SDK package placeholder.
- [x] Add initial configuration loading, database models, and a migration revision.
- [x] Add API readiness check for database connectivity.
- [x] Add exact-origin CORS allowlist configuration for browser checkout.
- [ ] Complete structured logging and production configuration validation.

## Phase 1a — Initial merchant and payment API slice

- [x] Add merchant registration with a one-time API key response and hashed key storage.
- [x] Add merchant-scoped payment intent creation, retrieval, listing, and cancellation.
- [x] Use integer USDC base units and require an idempotency key for payment creation.
- [x] Add initial SQLAlchemy models and Alembic revision.
- [x] Add API integration tests for idempotency, validation, and merchant isolation.
- [ ] Add safe production merchant onboarding, key rotation/revocation, and rate limiting.
- [ ] Verify database migration and API runtime against local PostgreSQL.

The merchant endpoints create and manage payment intents. The API also has request-driven transaction verification; see Phase 1b for periodic worker reconciliation. Full event indexing, merchant fulfillment reconciliation, and dead-letter operations remain outstanding.

## Phase 1b — Local container and CI scaffolding

- [x] Add non-root API, worker, and web Dockerfiles.
- [x] Extend Compose with service dependencies, health checks, PostgreSQL, and Redis.
- [x] Add GitHub Actions checks for web lint/build and API/worker lint/tests.
- [ ] Execute Docker builds and Compose startup in an environment with the Compose plugin.
- [x] Implement the Solidity Payment Router with OpenZeppelin SafeERC20, Ownable, and ReentrancyGuard.
- [x] Add local mock-ERC20 Foundry tests for direct transfers, approvals, ID reuse, invalid recipients, amounts, unsupported tokens, and token configuration access control.
- [x] Compile and execute Foundry tests locally with Foundry 1.8.6 / solc 0.8.28 (8 passed).
- [x] Add reproducible OpenZeppelin installation instructions for clean checkouts (vendor directory is ignored).
- [x] Add API-side Base Sepolia receipt and `PaymentReceived` event verification, confirmation tracking, and transaction persistence.
- [x] Add public checkout data and transaction verification endpoints; the API derives the contract payment ID as `keccak256(UTF-8 payment intent public ID)`.
- [x] Add a hosted checkout for injected wallets: Base Sepolia switch, USDC balance/allowance checks, approval, router payment, transaction link, and API-driven verification retry/polling.
- [x] Add worker-based confirmation polling, lease-based claims, retry backoff, and reorg reconciliation.
- [x] Add worker tests for confirmation thresholds, missing receipts, transient RPC errors, idempotency, lease contention, reverted transactions, and reorg recovery.
- [x] Add local Anvil integration test for an actual PaymentRouter payment reaching its configured confirmation threshold.
- [x] Persist browser-submitted checkout transaction hashes across page reloads and prevent repeated payment submission while verification is pending.
- [x] Reject mismatched Base Sepolia USDC configuration and require a public HTTPS API URL in production web builds.
- [x] Restrict local PostgreSQL and Redis host port bindings to loopback and align the environment example with Compose ports.
- [x] Prevent reusing a transaction hash for multiple payment intents at the model and migration level.
- [x] Compare the chain block timestamp with intent expiry, and record late mined payments as expired.
- [x] Reconcile status after detectable chain reorgs; temporary RPC inconsistency remains non-terminal.
- [x] Add persistent background confirmation and canonical-receipt reconciliation in the worker.
- [ ] Add API rate limiting and production-grade merchant authentication/key management.

The API verifier checks the chain ID, router destination, token configured on the router at the receipt block, event ID, payer, merchant recipient, token, amount, transaction status, canonical block hash, and confirmation count. It validates the configured token against the documented Base Sepolia USDC address. The worker reconciles submitted transaction hashes and previously observed receipts in bounded batches with leases, backoff, and a Redis heartbeat. The public checkout verification endpoint validates evidence before changing payment state but does not yet have rate limiting. Wallet checkout requires a deployed router address configured by the operator; no deployment has been performed. A transaction may be recorded as expired if its block timestamp is later than the payment-intent expiry; funds are nevertheless transferred directly to the merchant by the router. Reorg monitoring is eventual and cannot automatically reverse merchant fulfillment.

## Phase 2 — Core platform

- [ ] Define customer, wallet, and ledger domain models (merchant/payment-intent models exist; tenant isolation remains basic).
- [ ] Implement authentication, authorization, idempotency, and audit events.
- [ ] Implement payment lifecycle and reconciliation workflows.
- [ ] Define chain and stablecoin support with operational limits.
- [x] Add worker reconciliation jobs and bounded retry/backoff behavior.
- [ ] Add dead-letter/manual-review handling for long-lived unresolved payments.
- [ ] Add API contract documentation and SDK methods.

## Phase 3 — Production readiness

- [ ] Threat model and independent smart contract/security review.
- [ ] Add integration, contract, and end-to-end test coverage.
- [ ] Add observability, alerting, backups, and incident runbooks.
- [ ] Add deployment manifests, secret management, and release automation.
- [ ] Complete compliance, privacy, and operational review before handling funds.
