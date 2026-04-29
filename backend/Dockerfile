FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

RUN apt-get update && apt-get install -y \
    python3.12 \
    python3-pip \
    python3.12-venv \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python3.12 -m pip install --no-cache-dir --upgrade pip

COPY backend/requirements.txt .
RUN python3.12 -m pip install --no-cache-dir -r requirements.txt

COPY crypto /app/crypto
COPY backend/app /app/app

ENV PYTHONPATH="/app/crypto:/app"

EXPOSE 8000

CMD ["python3.12", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
