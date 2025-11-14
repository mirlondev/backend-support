from .base import *
import dj_database_url
import os
from pathlib import Path
from dotenv import load_dotenv

# ------------------------------------------------------------------
# BASE
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = False

# IMPORTANT POUR RAILWAY
ALLOWED_HOSTS = ["*", "backend-support-production.up.railway.app"]

# ------------------------------------------------------------------
# DATABASE
# Railway injecte DATABASE_URL automatiquement
# ------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=True,
    )
}


# ------------------------------------------------------------------
# STATIC & MEDIA
# ------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# WhiteNoise
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")


# ------------------------------------------------------------------
# CORS : autoriser ton frontend React
# ------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    "https://ton-frontend.vercel.app",
]

# ------------------------------------------------------------------
# CLOUDINARY
# ------------------------------------------------------------------
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.getenv("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": os.getenv("CLOUDINARY_API_KEY"),
    "API_SECRET": os.getenv("CLOUDINARY_API_SECRET"),
    "secure": True,
}

DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

# ------------------------------------------------------------------
# TWILIO
# ------------------------------------------------------------------
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

# ------------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "tcikets": {"handlers": ["console"], "level": "DEBUG"},
        "cloudinary": {"handlers": ["console"], "level": "DEBUG"},
    },
}

# Correction Django pour les FileField
from django.db.models import FileField
FileField.default_max_length = 500
