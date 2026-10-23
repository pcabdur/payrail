# Deployment

Production deployment is not configured. The web app can be deployed as a separate Vercel project; the FastAPI API, ARQ worker, PostgreSQL, and Redis need separately hosted services. Vercel hosting for the web app alone does not make payment creation or verification available: the API must be reachable over HTTPS and have its own database, Redis, and Base Sepolia RPC configuration.

## Deploy the web app to Vercel

1. Push the repository to GitHub and import `pcabdur/payrail` as a new Vercel project.
2. Configure the project for this pnpm monorepo and select `apps/web` as its application root. Use the detected Next.js framework settings and ensure the build uses the repository's pnpm workspace and root lockfile. Vercel documents the monorepo root-directory setup [here](https://vercel.com/docs/monorepos).
3. Set `NEXT_PUBLIC_API_URL` to the public HTTPS origin of the deployed API. This value is compiled into the browser bundle at build time, so set it before deploying and redeploy after changing it. It is public configuration; never put credentials or secrets in a `NEXT_PUBLIC_` variable.
4. After the first successful deployment, use the Vercel-provided web URL as an allowed browser origin in the API's `CORS_ORIGINS` configuration. Add the production and preview origins only when intended.

The API URL and Vercel URL do not exist until the corresponding services are deployed; use the provider-generated HTTPS URLs rather than guessing them. Configure `CORS_ORIGINS` on the API host, not as a web-app secret. The API's database URL, Redis URL, RPC URL, and other private settings belong in that host's secret environment configuration.

## Deploy the API and worker

Deploy the API and worker as separate long-running/container services on a host that supports FastAPI and ARQ. Provision managed PostgreSQL and Redis, configure private secrets, enable TLS at the public API ingress, and run Alembic migrations as a controlled release step before routing traffic. Use separate staging and production resources. Do not use Compose's local development credentials in hosted environments. The worker needs the same database, Redis, RPC endpoint, router address, token address, and confirmation settings as the API.

The root Compose file is for local development, not a production deployment. The worker uses database row leases and a Redis heartbeat, but this repository has no external alert delivery, dead-letter/manual-review workflow, merchant fulfillment reconciliation, rate limits, production merchant onboarding/key controls, or independent contract/security review. Reorg checks are periodic; operators need an explicit fulfillment finality policy before accepting funds. No contract deployment is performed by these instructions.
