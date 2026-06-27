# Dockerfile for SBI Sarathi Backend MVP
FROM python:3.11-slim

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files
COPY app.py .
COPY conversation_agent.py .
COPY qualification_agent.py .
COPY signal_agent.py .
COPY signal_router.py .
COPY db.py .
COPY propensity_model.pkl .
COPY data/ ./data/

# Expose port
EXPOSE 8000

# Start server
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
