FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

WORKDIR /workspace
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY app ./app
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2,<3" \
    && pip install --no-cache-dir ".[app,export]"

EXPOSE 7860
CMD ["python", "app/app.py"]
