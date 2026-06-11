FROM python:3.11-slim
WORKDIR /app
COPY python/graphql/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY python/graphql/app.py .
EXPOSE 8012
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8012", "--workers", "4"]
