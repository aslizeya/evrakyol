# Derleme bağlamı depo köküdür: docker build -f apps/web/Dockerfile .
# Yayında web uygulaması Vercel'de çalışır; bu imaj yerel tam yığın denemesi içindir.
FROM node:24-alpine AS deps
WORKDIR /repo/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
COPY apps/web/prisma ./prisma
COPY apps/web/prisma7.config.ts ./
RUN npm ci

FROM node:24-alpine AS build
WORKDIR /repo
COPY --from=deps /repo/apps/web/node_modules ./apps/web/node_modules
COPY apps/web ./apps/web
COPY config ./config
WORKDIR /repo/apps/web
ENV NEXT_TELEMETRY_DISABLED=1
RUN npx prisma generate && npm run build

FROM node:24-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /repo/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=node:node /repo/apps/web/public ./apps/web/public
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
