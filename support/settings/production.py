from .base import *
import dj_database_url
import os

DEBUG = False
ALLOWED_HOSTS = ["ton-projet.onrender.com"]

# Base de données Render
DATABASES = {
    'default': dj_database_url.config(conn_max_age=600, ssl_require=True)
}

# Static & media
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# WhiteNoise pour les fichiers statiques
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# CORS : autoriser ton frontend React sur Vercel
CORS_ALLOWED_ORIGINS = [
    "https://ton-frontend.vercel.app",
]

# Variables sensibles (à mettre dans Render)
SECRET_KEY = os.environ.get("SECRET_KEY")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
