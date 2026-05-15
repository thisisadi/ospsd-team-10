FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
COPY src ./src

RUN uv sync --all-packages --frozen

ENV PATH="/app/.venv/bin:$PATH"

# AWS App Runner expects port 8080
ENV PORT=8080
EXPOSE 8080

# Start FastAPI app
CMD ["uvicorn", "vertical_service.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
