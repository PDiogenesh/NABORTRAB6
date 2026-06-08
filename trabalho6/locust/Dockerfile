FROM python:3.11-slim
WORKDIR /locust
COPY locust/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY locust/ .
EXPOSE 8089
ENTRYPOINT ["locust", "--web-host", "0.0.0.0"]
