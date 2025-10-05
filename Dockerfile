# Dockerfile
FROM python:3.13-slim

# Install uv and make (optional if you want to use Makefile)
RUN pip install uv && apt-get update && apt-get install -y make && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Install dependencies system-wide (no venv)
RUN uv pip install --system -e .

EXPOSE 8000

# Production entrypoint (same as `make run`, but without reload)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
