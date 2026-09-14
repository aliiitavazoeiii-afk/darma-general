from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("sales/", views.sale_calendar, name="sale_start"),
    path("sales/select/<int:jy>/<int:jm>/<int:jd>/", views.select_sale_day, name="select_sale_day"),
    path("sales/<int:day_id>/", views.sale_day, name="sale_day"),
    path("report/", views.report, name="report"),
    path("inventory/", views.inventory, name="inventory"),
    path("returns/", views.returns, name="returns"),
    path("purchase/", views.purchase, name="purchase"),
    path("finance/", views.finance, name="finance"),
    path("settings/", views.settings_home, name="settings_home"),
]
