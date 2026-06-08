FROM python:3.11-slim
WORKDIR /app
COPY python/grpc/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Generate Python gRPC code from proto
COPY music.proto .
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. music.proto
COPY python/grpc/app.py .
EXPOSE 8013
CMD ["python", "app.py"]
