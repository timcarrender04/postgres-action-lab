# This image is the API process. Postgres is the other Compose service.
# Binding 0.0.0.0 is what makes port 8000 reachable from the laptop.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
