FROM python:3.12-slim

WORKDIR /app

COPY requirements-serve.txt .
RUN pip install --no-cache-dir -r requirements-serve.txt

COPY app ./app
COPY data/catalog.sqlite ./data/catalog.sqlite

# Railway injects PORT (usually 8080) and routes the public domain to that port.
# Do not EXPOSE 8000: that makes the domain target port 8000 while Uvicorn listens on 8080.
CMD ["/bin/sh", "-c", "exec python -m app.main --host 0.0.0.0 --port ${PORT:-8080}"]
