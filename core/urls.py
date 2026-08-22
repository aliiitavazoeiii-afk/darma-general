from django.urls import path
from . import views
urlpatterns=[
 path("",views.dashboard,name="dashboard"),
 path("sales/",views.sale_start,name="sale_start"),
 path("sales/<int:day_id>/",views.sale_brand,name="sale_brand"),
 path("sales/<int:day_id>/<int:brand_id>/<int:size_id>/",views.sale_size,name="sale_size"),
 path("sales/save/",views.sale_line_save,name="sale_line_save"),
 path("inventory/",views.inventory,name="inventory"),
 path("report/",views.report,name="report"),
 path("settings/products/",views.settings_products,name="settings_products"),
]
