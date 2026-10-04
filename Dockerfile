# Multi-stage: build the UI, then run the API + static UI from one Python image.
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY --from=web /web/dist ./frontend/dist
ENV AGENCYOS_DATA_DIR=/data AGENCYOS_FRONTEND_DIST=/app/frontend/dist
RUN mkdir -p /data && chown 1000 /data
VOLUME /data
WORKDIR /app/backend
EXPOSE 8000
USER 1000
CMD ["python", "-m", "agencyos", "--host", "0.0.0.0", "--port", "8000"]
