
FROM python:3.11-slim

WORKDIR /app


COPY requirements.txt .


RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


COPY . .


EXPOSE 8000


CMD ["python", "app.py"]



