FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml

RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir "uvicorn[standard]" "fastapi" "httpx" "pydantic" "pydantic-settings"

COPY app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
