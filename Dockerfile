# One image, one service: Django serves both the API and the built React app.

# 1. Build the React app.
FROM node:24-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2. Django under gunicorn, with the built app next to it.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_PRODUCTION=true \
    FRONTEND_DIST=/app/frontend
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /frontend/dist /app/frontend
RUN useradd --create-home app
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi", "--config", "gunicorn.conf.py"]
