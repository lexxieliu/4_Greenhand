from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Password reset emails print to the terminal. Swap for a real provider (PRD: SendGrid/SES) in production.
EMAIL_BACKEND = "greenhand.email_backends.PlainConsoleEmailBackend"
