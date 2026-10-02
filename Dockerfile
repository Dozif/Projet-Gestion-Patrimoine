FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATRIMOINE_DATA_DIR=/data \
    PATRIMOINE_STATIC_ROOT=/app/staticfiles

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN DJANGO_DEBUG=1 python manage.py collectstatic --noinput \
    && useradd --uid 1000 --create-home patrimoine \
    && mkdir -p /data \
    && chown -R patrimoine:patrimoine /data

EXPOSE 8000
ENTRYPOINT ["sh", "/app/docker/entrypoint.sh"]
