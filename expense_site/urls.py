from django.contrib.auth import views as auth_views
from django.urls import include, path

from core import calendar_views
from expense_tracker import pwa

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="expense_tracker/login.html"),
        name="expense_login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="expense_logout"),
    path("manifest.webmanifest", pwa.manifest, name="expense_manifest"),
    path("sw.js", pwa.service_worker, name="expense_service_worker"),
    path("calendar/picker/", calendar_views.jalali_picker, name="expense_calendar_picker"),
    path("", include("expense_tracker.urls")),
]
