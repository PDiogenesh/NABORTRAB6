FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libxml2-dev libxslt-dev && rm -rf /var/lib/apt/lists/*
COPY python/soap/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY python/soap/app.py .
EXPOSE 8014
CMD ["python", "app.py"]
