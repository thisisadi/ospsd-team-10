FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY src ./src

RUN uv sync --all-packages --frozen

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["python", "-m", "vertical_service"]
