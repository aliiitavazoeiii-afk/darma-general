from django.urls import path
from . import daily_views, views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("sales/", daily_views.sale_calendar, name="sale_start"),
    path("sales/select/<int:jy>/<int:jm>/<int:jd>/", daily_views.select_sale_day, name="select_sale_day"),
    path("sales/<int:day_id>/", views.sale_brand, name="sale_brand"),
    path("sales/<int:day_id>/report/", daily_views.daily_report, name="daily_report"),
    path("sales/<int:day_id>/<int:brand_id>/<int:size_id>/", daily_views.sale_size, name="sale_size"),
    path("sales/save/", views.sale_line_save, name="sale_line_save"),
    path("inventory/", views.inventory, name="inventory"),
    path("report/", views.report, name="report"),
    path("settings/", views.settings_home, name="settings_home"),
    path("settings/catalog/", views.settings_catalog, name="settings_catalog"),
    path("settings/products/", views.settings_products, name="settings_products"),
    path("settings/products/new/", views.settings_product_form, name="settings_product_new"),
    path("settings/products/<int:product_id>/", views.settings_product_form, name="settings_product_edit"),
    path("settings/stock/", views.settings_stock, name="settings_stock"),
    path("settings/finance/", views.settings_finance, name="settings_finance"),
    path("settings/rules/", views.settings_rules, name="settings_rules"),
]
