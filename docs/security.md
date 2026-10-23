# Security

This scaffold is not ready to handle funds or production data. The API has a development bearer API-key mechanism and merchant scoping, but no user authentication, key rotation/revocation, rate limiting, webhook security, or production key management. The Payment Router uses an owner-controlled token configuration, but has not been compiled or independently reviewed. Keep credentials in an approved secret manager and out of source control. Use least privilege, audit sensitive operations, and complete an independent review before any funds are at risk.
