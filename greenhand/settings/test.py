"""Settings for `python manage.py test --settings=greenhand.settings.test` and CI.

Tests run on an in-memory SQLite database so they never create test databases on the shared
Supabase instance and need no GDAL/PostGIS or network. The garden and plant models use no
PostgreSQL-only fields, so behaviour matches production.
"""
import tempfile

from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
MEDIA_ROOT = tempfile.mkdtemp(prefix='greenhand-test-media-')
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
