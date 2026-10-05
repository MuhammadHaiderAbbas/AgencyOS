# JARVIS — multi-stage: build web, then run gateway
FROM node:22-slim AS web
WORKDIR /web
COPY apps/web/package.json ./
RUN npm install
COPY apps/web/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
COPY --from=web /web/dist ./apps/web/dist
ENV JARVIS_DATA_DIR=/data JARVIS_FRONTEND_DIST=/app/apps/web/dist PYTHONPATH=/app
RUN mkdir -p /data && chmod 777 /data
EXPOSE 8000
CMD ["python", "-m", "apps.gateway.main", "--host", "0.0.0.0", "--port", "8000"]
