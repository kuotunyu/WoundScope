FROM node:24-alpine AS frontend-build

WORKDIR /workspace/frontend
RUN corepack enable && corepack prepare pnpm@11.16.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend ./
RUN pnpm build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY app ./app
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2,<3" \
    && pip install --no-cache-dir ".[app,export]"
COPY --from=frontend-build /workspace/frontend/dist ./frontend/dist

EXPOSE 7860
CMD ["python", "app/app.py"]
