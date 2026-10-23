# Demo status

The current demo is limited to registering a development merchant and creating/listing/canceling pending payment intents. Run API migrations, start the API, register a merchant at `POST /v1/merchants`, and use the returned API key as a Bearer token for `/v1/payment_intents` requests. Include `Idempotency-Key` on create requests and send `amount` as integer USDC base units.

There is no wallet checkout, deployed contract, live exchange-rate quote, blockchain verification, webhook, refund, or testnet payment flow. A pending record is not proof of payment.
