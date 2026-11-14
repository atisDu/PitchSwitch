# Pitchlist frontend (Next.js). Build from the repo root:
#   docker build -f deploy/frontend.Dockerfile -t pitchlist-frontend .
# API_URL is where the Next.js server reaches the backend inside the compose network.
# Browser requests to /api/* never reach Next.js: Caddy sends them straight to the backend.
FROM node:22-slim AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
ARG API_URL=http://api:8000
ENV API_URL=${API_URL} NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-slim
WORKDIR /app/frontend
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 API_URL=http://api:8000 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/frontend ./
USER node
EXPOSE 3000
CMD ["npm", "run", "start"]
