FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ARG IPOCKET_VERSION=dev
ARG IPOCKET_COMMIT=unknown
ARG IPOCKET_BUILD_TIME=unknown

ENV IPOCKET_VERSION=${IPOCKET_VERSION} \
    IPOCKET_COMMIT=${IPOCKET_COMMIT} \
    IPOCKET_BUILD_TIME=${IPOCKET_BUILD_TIME}

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

EXPOSE 8000

ENV IPAM_DB_PATH=/data/ipocket.db
VOLUME ["/data"]

CMD ["/bin/sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
