#!/bin/bash
python manage.py collectstatic --noinput
gunicorn support.wsgi:application --bind 0.0.0.0:$PORT
