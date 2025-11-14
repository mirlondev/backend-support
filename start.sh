#!/bin/bash

# Donner les permissions d'exécution au script dans support/
bash support/start.sh

python manage.py collectstatic --noinput
gunicorn support.wsgi:application --bind 0.0.0.0:$PORT
