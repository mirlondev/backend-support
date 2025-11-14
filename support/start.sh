#!/bin/bash

# Donner les permissions d'exécution au script dans support/
chmod +x support/start.sh


#!/bin/bash

# Aller dans le bon répertoire
cd /support

# Collecter les fichiers statiques
python manage.py collectstatic --noinput

# Appliquer les migrations
python manage.py migrate --noinput

# Démarrer Gunicorn
gunicorn support.wsgi:application --bind 0.0.0.0:8000 --workers 4
