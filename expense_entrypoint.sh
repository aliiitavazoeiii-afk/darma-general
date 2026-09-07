#!/bin/sh
set -eu

python manage.py migrate expense_tracker --settings=expense_site.settings --noinput
python manage.py collectstatic --settings=expense_site.settings --noinput

exec gunicorn expense_site.wsgi:application   --bind 0.0.0.0:8000   --workers 2   --threads 2   --timeout 60   --access-logfile -   --error-logfile -
