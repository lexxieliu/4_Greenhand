FROM python:3.12-slim

# gdal/geos: the database engine is PostGIS, which loads them at start-up.
RUN apt-get update && apt-get install -y --no-install-recommends gdal-bin libgeos-c1v5 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV DJANGO_SETTINGS_MODULE=greenhand.settings.production
# collectstatic only needs settings to load; the real values come from the platform at run time.
RUN SECRET_KEY=build ALLOWED_HOSTS=build DATABASE_URL=postgis://build:build@localhost/build python manage.py collectstatic --noinput

EXPOSE 8000
# One worker: each worker would load its own copy of the ~6 GB local model. Threads serve concurrent requests.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn greenhand.wsgi --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 120"]
