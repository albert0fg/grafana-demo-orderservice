FROM python:3.12-slim

WORKDIR /app

ARG GIT_SHA=dev
ENV SERVICE_VERSION=$GIT_SHA

COPY order-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/telemetry.py .
COPY order-service/main.py .

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
