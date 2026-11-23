FROM python:3.12-slim

WORKDIR /app

COPY requirements-serve.txt .
RUN pip install --no-cache-dir -r requirements-serve.txt

COPY app ./app
COPY data/catalog.sqlite ./data/catalog.sqlite

ENV PORT=8000
EXPOSE 8000

CMD python -m app.main --host 0.0.0.0 --port $PORT
