from django.urls import path

from . import business_tools_v5, calendar_views, catalog_v5, daily_views, excel_dashboard, excel_sales, final_views, inventory_v5, material_report_v5, pricing_v7, report_v5, settings_stock_v5, takvin_v5, views

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

    path("report/", report_v5.report, name="report"),
    path("report/manual/", report_v5.manual_report_action, name="manual_report_action"),
    path("report/financial-summary/", business_tools_v5.financial_summary, name="financial_summary"),
    path("material-report/", material_report_v5.material_report, name="material_report"),
    path("material-report/<int:block_id>/save/", material_report_v5.material_block_save, name="material_block_save"),
    path("material-report/<int:block_id>/delete/", material_report_v5.material_block_delete, name="material_block_delete"),
    path("takvin/", takvin_v5.takvin_excel, name="takvin"),

    path("payments/", business_tools_v5.payments, name="payments"),
    path("payments/add/", business_tools_v5.payment_add, name="payment_add"),
    path("payments/<int:payment_id>/delete/", business_tools_v5.payment_delete, name="payment_delete"),
    path("payments/mellat/set/", business_tools_v5.mellat_set, name="mellat_set"),
    path("calculator/", business_tools_v5.calculator, name="calculator"),
    path("calculator/quote/", business_tools_v5.calculator_quote, name="calculator_quote"),

    path("inventory/", inventory_v5.inventory, name="inventory"),
    path("inventory/color-model/add/", inventory_v5.add_color_model, name="inventory_add_color_model"),
    path("inventory/operations/", final_views.inventory_operations, name="inventory_operations"),

    path("materials/", final_views.materials, name="materials"),
    path("production/", final_views.production, name="production"),
    path("finance/", final_views.finance, name="finance"),
    path("expenses/", final_views.expenses, name="expenses"),
    path("assets/", final_views.assets, name="assets"),
    path("returns/", final_views.returns, name="returns"),

    path("settings/", views.settings_home, name="settings_home"),
    path("settings/catalog/", catalog_v5.settings_catalog, name="settings_catalog"),
    path("settings/products/", pricing_v7.settings_products, name="settings_products"),
    path("settings/products/new/", views.settings_product_form, name="settings_product_new"),
    path("settings/products/<int:product_id>/", views.settings_product_form, name="settings_product_edit"),
    path("settings/stock/", settings_stock_v5.settings_stock, name="settings_stock"),
    path("settings/finance/", views.settings_finance, name="settings_finance"),
    path("settings/rules/", views.settings_rules, name="settings_rules"),
]
