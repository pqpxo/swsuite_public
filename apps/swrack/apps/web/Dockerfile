# version 26
FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json vite.config.ts svelte.config.js index.html ./
COPY src ./src
COPY static ./static
# Mount path baked into the bundle's asset and API URLs.
ARG BASE_PATH=/
ENV BASE_PATH=$BASE_PATH
RUN npm run build

FROM nginx:stable-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
