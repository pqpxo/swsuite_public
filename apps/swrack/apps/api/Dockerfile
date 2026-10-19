# version 20
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json ./
COPY prisma ./prisma
RUN npx prisma generate

COPY src ./src
RUN npm run build

FROM node:22-alpine AS runtime

WORKDIR /app
ENV NODE_ENV=production

COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/prisma ./prisma
COPY --from=build /app/dist ./dist
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN apk add --no-cache iputils \
  && chmod 4755 "$(command -v ping)" \
  && chmod +x ./docker-entrypoint.sh \
  && mkdir -p /data/assets/original /data/assets/optimised /data/assets/thumbnails \
  && chown -R node:node /app /data

USER node
EXPOSE 8080

ENTRYPOINT ["./docker-entrypoint.sh"]
