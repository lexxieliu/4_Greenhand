"""Settings for the test suite and CI: SQLite in memory, no external services."""
import tempfile

from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ['testserver']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
MEDIA_ROOT = tempfile.mkdtemp(prefix='greenhand-test-media-')
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
