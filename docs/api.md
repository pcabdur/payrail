# API

# API

FastAPI exposes interactive OpenAPI docs at `/docs` while running. Merchant registration and payment-intent operations are available under `/v1`; merchant endpoints require the one-time-issued development API key as a Bearer token.

Browser CORS is controlled by `CORS_ORIGINS`, a comma-separated exact-origin allowlist (defaults to `http://localhost:3000`).

## Payment endpoints

- `POST /v1/payment_intents` — create a payment with integer USDC base units and an `Idempotency-Key` header.
- `GET /v1/payment_intents` and `GET /v1/payment_intents/{public_id}` — list or retrieve the authenticated merchant's intents.
- `POST /v1/payment_intents/{public_id}/cancel` — cancel an unpaid intent.
- `POST /v1/payment_intents/{public_id}/verify` — verify a submitted transaction hash against Base Sepolia RPC evidence.
- `GET /checkout/{public_id}` — return public checkout details and the configured chain/token/router addresses.
- `POST /checkout/{public_id}/verify` — submit a transaction hash for the same server-side evidence verification, without merchant credentials.

## Verification behavior

The verifier requires `BASE_SEPOLIA_RPC_URL`, `PAYMENT_ROUTER_ADDRESS`, and `USDC_TOKEN_ADDRESS`. It checks chain ID 84532, successful receipt status, router destination, the router's configured token at the payment block, and one matching `PaymentReceived` event. The event ID is `keccak256(UTF-8 payment intent public_id)`. It checks that payer matches the transaction sender, recipient matches the intent, and event token matches configured USDC. The API records the log and confirmation count, marking exact amounts `succeeded` after the configured minimum; differing amounts become `underpaid` or `overpaid` after that threshold.

The ARQ worker independently revisits submitted transactions, including those first seen before mining, and rechecks previously confirmed receipts for canonical block changes and transaction membership in the original block. It uses PostgreSQL row locks (`SKIP LOCKED`) plus expiring per-payment leases, bounded batches and RPC concurrency, configurable polling with transient/missing-receipt backoff capped at five minutes, and provider timeouts. Configure it with `PAYMENT_RECONCILE_INTERVAL_SECONDS`, `PAYMENT_RECONCILE_BATCH_SIZE`, `RPC_TIMEOUT_SECONDS`, and `PAYMENT_MIN_CONFIRMATIONS`. It runs as `arq payrail_worker.worker.WorkerSettings` and updates Redis heartbeat/metrics keys for Compose health and operator inspection. Public checkout verification still needs rate limiting.

Payment states used by reconciliation are `confirming` while the receipt is missing or below the confirmation threshold, and `succeeded`, `underpaid`, `overpaid`, or `expired` after the threshold. If the receipt disappears and the original block is no longer canonical, the payment and transaction move to `reorged` and an error-level operational log asks operators to review merchant fulfillment. A later valid inclusion is reverified and can move back through `confirming` to its amount/expiry result. A canonical reverted receipt for a never-verified submission is marked `failed`; temporary provider errors preserve the last known state. The worker does not reverse an already-delivered product or service. Local Anvil tests simulate a deterministic block-hash change through a verifier fixture; they do not prove behavior under every real network reorganization.

The worker polls at a bounded frequency and can eventually detect a reorg, but a merchant must define its own fulfillment finality policy. An already displayed `succeeded` state can be stale between reconciliation passes. The hosted checkout uses wagmi/viem with an injected browser wallet, but successful payment status still comes only from the API's verified evidence. Do not interpret a returned transaction hash alone as a successful payment.
