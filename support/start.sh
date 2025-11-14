#!/bin/bash
# Start Django app
gunicorn support.wsgi:application --bind 0.0.0.0:$PORT
