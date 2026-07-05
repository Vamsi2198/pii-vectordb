FROM python:3.11-slim

WORKDIR /app

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy source and install Python deps
COPY requirements.txt ./
RUN python -m pip install --upgrade pip
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8000

ENV PORT 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "${PORT}"]
