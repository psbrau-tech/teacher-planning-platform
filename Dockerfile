FROM node:22-bookworm-slim AS frontend-build

WORKDIR /src/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
ARG VITE_SUPABASE_URL=""
ARG VITE_SUPABASE_ANON_KEY=""
ENV VITE_SUPABASE_URL=${VITE_SUPABASE_URL}
ENV VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY}
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TPP_FRONTEND_DIST_PATH=/app/frontend-dist

WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/assets ./assets
RUN python -m pip install --upgrade pip \
    && python -m pip install .

COPY --from=frontend-build /src/frontend/dist /app/frontend-dist

RUN useradd --create-home --uid 10001 tpp \
    && chown -R tpp:tpp /app
USER tpp

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "app.runtime:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
