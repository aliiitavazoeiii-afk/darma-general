from config.settings import *  # noqa: F401,F403
import os

INSTALLED_APPS = [*INSTALLED_APPS, "expense_tracker"]
ROOT_URLCONF = "expense_site.urls"
WSGI_APPLICATION = "expense_site.wsgi.application"
STATIC_ROOT = BASE_DIR / "staticfiles_expense"

ALLOWED_HOSTS = [
    x.strip()
    for x in os.getenv("EXPENSE_ALLOWED_HOSTS", "*").split(",")
    if x.strip()
]
CSRF_TRUSTED_ORIGINS = [
    x.strip()
    for x in os.getenv("EXPENSE_CSRF_TRUSTED_ORIGINS", "").split(",")
    if x.strip()
]

SESSION_COOKIE_NAME = "darma_expense_sessionid"
CSRF_COOKIE_NAME = "darma_expense_csrftoken"
EXPENSE_USE_HTTPS = os.getenv("EXPENSE_USE_HTTPS", "0") == "1"
SESSION_COOKIE_SECURE = EXPENSE_USE_HTTPS
CSRF_COOKIE_SECURE = EXPENSE_USE_HTTPS

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "/tmp/darma-expense-cache",
        "TIMEOUT": 300,
        "OPTIONS": {"MAX_ENTRIES": 300},
    }
}
