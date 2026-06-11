FROM python:3.11-slim
WORKDIR /app
COPY python/rest/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY python/rest/app.py .
EXPOSE 8011
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8011", "--workers", "4"]
