# Multi-stage build: build frontend assets, then serve via slim image
FROM node:20-alpine AS builder
WORKDIR /build

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY tsconfig.json vite.config.ts tailwind.config.js postcss.config.js index.html ./
COPY src ./src
RUN npm run build

# ── Runtime stage ──
FROM python:3.11-slim
WORKDIR /app

# Copy built assets and lightweight server
COPY --from=builder /build/dist ./dist
COPY server.py ./

ENV DASHBOARD_PORT=80
ENV DASHBOARD_BACKEND_URL=http://football-data-mcp:8910

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:80/', timeout=3).read()" || exit 1
CMD ["python", "server.py"]
