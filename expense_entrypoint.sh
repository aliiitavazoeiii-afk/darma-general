#!/bin/sh
set -eu

python manage.py migrate expense_tracker --settings=expense_site.settings --noinput
python manage.py collectstatic --settings=expense_site.settings --noinput

exec gunicorn expense_site.wsgi:application \
  --bind 0.0.0.0:8000 \
  --worker-class sync \
  --workers 3 \
  --timeout 60 \
  --graceful-timeout 20 \
  --max-requests 250 \
  --max-requests-jitter 50 \
  --worker-tmp-dir /dev/shm \
  --access-logfile - \
  --error-logfile -
