import environ
from pathlib import Path

#initiate env file
env = environ.Env()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

#load env file
environ.Env.read_env(BASE_DIR / ".env")