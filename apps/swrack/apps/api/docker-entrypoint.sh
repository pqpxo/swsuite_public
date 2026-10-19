#!/bin/sh
# version 2
set -eu

npx prisma db push --skip-generate
node dist/prisma/seed.js
exec node dist/src/server.js
