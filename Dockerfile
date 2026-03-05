FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ARG API_PORT=8000
ENV API_PORT=${API_PORT}

WORKDIR /app

# system deps for healthchecks and postgres client libs
RUN apt-get update && apt-get install -y curl build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE ${API_PORT}

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${API_PORT}"]
