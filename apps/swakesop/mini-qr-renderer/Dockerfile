# version 1
FROM node:22-bookworm-slim
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev

COPY server.js ./
COPY config ./config

ENV PORT=3000
EXPOSE 3000

CMD ["npm", "start"]
