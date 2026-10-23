FROM node:22-alpine

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /workspace

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/sdk/package.json ./packages/sdk/package.json

RUN pnpm install --frozen-lockfile

COPY apps/web ./apps/web
COPY packages/sdk ./packages/sdk

# Make the public API URL available during the Next.js build.
ARG NEXT_PUBLIC_API_URL=http://localhost:8001
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN pnpm --filter @payrail/web build

USER node

EXPOSE 3000

CMD ["pnpm", "--filter", "@payrail/web", "start"]