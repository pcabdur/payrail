# Threat model (initial scope)

## Assets

- Merchant API credentials and account/payment metadata.
- Correctness of pending payment intent amounts and recipients.
- Future blockchain transaction evidence and webhook secrets.

## Trust boundaries and current controls

- API key bearer authentication is scoped to a merchant. Keys are returned once and stored as SHA-256 hashes; generated keys have high entropy.
- Payment creation requires a merchant-scoped idempotency key and stores integer USDC base units.
- Payment records start in `requires_payment`; no API route marks a payment successful.

## Known gaps

There is no user login, rate limiting, key rotation/revocation, tenant membership system, CORS policy, webhook delivery, wallet integration, chain verification, API-to-contract integration, audit trail, or operational alerting. The standalone Payment Router has not been compiled, deployed, or independently reviewed. The merchant registration endpoint is a development onboarding helper without abuse controls. No real funds or sensitive production data should be handled.

Before a testnet payment feature, threat model wallet spoofing, wrong-network transactions, RPC compromise, duplicate/reorged events, confirmation depth, and recipient/amount mismatches. Before production, add independent review and key-management procedures. Never place private keys in the API.
