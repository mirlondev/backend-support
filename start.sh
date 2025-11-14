#!/bin/bash

# Se positionner dans le répertoire support où se trouve manage.py
cd /app/support

echo "=== Django Deployment Info ==="
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"
echo "Directory structure:"
ls -la
echo "=============================="

# Collecter les fichiers statiques
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Appliquer les migrations
echo "🗄️  Running database migrations..."
python manage.py migrate --noinput

# Démarrer Gunicorn
echo "🚀 Starting Gunicorn server..."
exec gunicorn support.wsgi:application \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers 4 \
    --worker-class sync \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --capture-output \
    --enable-stdio-inheritance