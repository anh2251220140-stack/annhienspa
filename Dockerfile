FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
COPY requirements-lock.txt /app/requirements-lock.txt

RUN pip install --no-cache-dir -r requirements.txt -c requirements-lock.txt mysqlclient \
    && pip install --no-cache-dir "gunicorn>=22,<24"

COPY . /app/

EXPOSE 8000

# Static output only; never migrate, seed or otherwise write the application DB.
CMD ["sh", "-c", "python manage.py collectstatic --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2"]
