#!/bin/bash

# Donner les permissions d'exécution au script dans support/
chmod +x support/start.sh

# Exécuter le script
./support/start.sh
python manage.py migrate

python manage.py collectstatic --noinput
gunicorn support.wsgi:application --bind 0.0.0.0:$PORT
