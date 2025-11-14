from .base import *
import dj_database_url
import os
from dotenv import load_dotenv
# ------------------------------------------------------------------
# BASE
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")          # charge le .env
SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Base de données Render
DATABASES = {
    'default': dj_database_url.config(conn_max_age=600, ssl_require=True)
}

# Static & media
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# WhiteNoise pour les fichiers statiques
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")


# CORS : autoriser ton frontend React sur Vercel
CORS_ALLOWED_ORIGINS = [
    "https://ton-frontend.vercel.app",
]


'''DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv(
            "DATABASE_URL",
            f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        )
    )
}'''

DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv(
            "DATABASE_URL",
        )
    )
    }
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.getenv("CLOUDINARY_CLOUD_NAME"),
    "API_KEY":os.getenv("CLOUDINARY_API_KEY"),
   "API_SECRET":os.getenv("CLOUDINARY_API_SECRET"),
     "secure":True,  # IMPORTANT pour HTTPS
    "api_proxy":None 
} 
# Variables sensibles (à mettre dans Render)
SECRET_KEY = os.environ.get("SECRET_KEY")

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")   # ✅ sans virgule
TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN")    # ✅ sans virgule
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER")
# settings/production.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'tcikets': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'cloudinary': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
# Configuration globale pour tous les FileField
from django.db.models import FileField
FileField.default_max_length = 500