from django.urls import path

from . import business_tools, calendar_views, catalog_views, daily_views, excel_dashboard, excel_sales, excel_takvin, final_views, inventory_views, material_report_v2, report_actions, report_v4, views

urlpatterns = [
    path("", excel_dashboard.dashboard, name="dashboard"),
    path("calendar/picker/", calendar_views.jalali_picker, name="jalali_picker"),
    path("sales/", daily_views.sale_calendar, name="sale_start"),
    path("sales/select/<int:jy>/<int:jm>/<int:jd>/", daily_views.select_sale_day, name="select_sale_day"),
    path("sales/<int:day_id>/", final_views.sale_brand, name="sale_brand"),
    path("sales/<int:day_id>/report/", daily_views.daily_report, name="daily_report"),
    path("sales/<int:day_id>/<int:brand_id>/<int:size_id>/", daily_views.sale_size, name="sale_size"),
    path("sales/save/", excel_sales.sale_line_save, name="sale_line_save"),
    path("sales/shortage/<int:shortage_id>/resolve/", excel_sales.shortage_resolve, name="shortage_resolve"),

    path("report/", report_v4.report, name="report"),
    path("report/manual/", report_actions.manual_report_action, name="manual_report_action"),
    path("report/financial-summary/", business_tools.financial_summary, name="financial_summary"),
    path("material-report/", material_report_v2.material_report, name="material_report"),
    path("material-report/<int:block_id>/save/", material_report_v2.material_block_save, name="material_block_save"),
    path("material-report/<int:block_id>/delete/", material_report_v2.material_block_delete, name="material_block_delete"),
    path("takvin/", excel_takvin.takvin_excel, name="takvin"),

    path("payments/", business_tools.payments, name="payments"),
    path("payments/add/", business_tools.payment_add, name="payment_add"),
    path("payments/<int:payment_id>/delete/", business_tools.payment_delete, name="payment_delete"),
    path("payments/mellat/set/", business_tools.mellat_set, name="mellat_set"),
    path("calculator/", business_tools.calculator, name="calculator"),
    path("calculator/quote/", business_tools.calculator_quote, name="calculator_quote"),

    path("inventory/", inventory_views.inventory, name="inventory"),
    path("inventory/color-model/add/", inventory_views.add_color_model, name="inventory_add_color_model"),
    path("inventory/operations/", final_views.inventory_operations, name="inventory_operations"),

    path("materials/", final_views.materials, name="materials"),
    path("production/", final_views.production, name="production"),
    path("finance/", final_views.finance, name="finance"),
    path("expenses/", final_views.expenses, name="expenses"),
    path("assets/", final_views.assets, name="assets"),
    path("returns/", final_views.returns, name="returns"),

    path("settings/", views.settings_home, name="settings_home"),
    path("settings/catalog/", catalog_views.settings_catalog, name="settings_catalog"),
    path("settings/products/", views.settings_products, name="settings_products"),
    path("settings/products/new/", views.settings_product_form, name="settings_product_new"),
    path("settings/products/<int:product_id>/", views.settings_product_form, name="settings_product_edit"),
    path("settings/stock/", views.settings_stock, name="settings_stock"),
    path("settings/finance/", views.settings_finance, name="settings_finance"),
    path("settings/rules/", views.settings_rules, name="settings_rules"),
]
