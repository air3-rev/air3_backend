# Dockerfile
FROM python:3.11-slim

# Install uv
RUN pip install uv

# Set workdir
WORKDIR /app

# Copy your project files
COPY . .

# Install dependencies
RUN uv pip install --system -e .

# Expose port 8000
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
