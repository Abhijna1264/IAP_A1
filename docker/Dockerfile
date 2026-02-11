FROM python:3.9-slim

# Install OS dependencies for bcrypt, etc.
RUN apt-get update && \
    apt-get install -y build-essential libssl-dev libffi-dev python3-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements from project root
COPY ../requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY ../src/server ./server

# Copy TLS certs
COPY ../server.crt ./server.crt
COPY ../server.key ./server.key

# Environment variables
ENV REDIS_HOST=redis
ENV SERVER_ID=server1

EXPOSE 65432

CMD ["python", "server/server.py"]
