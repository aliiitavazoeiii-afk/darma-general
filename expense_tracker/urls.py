from django.urls import path

from . import category_report_v8, expense_v7, export_xlsx, views

app_name = "expense_tracker"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("expenses/", expense_v7.expense_list, name="expense_list"),
    path("expenses/add/", expense_v7.expense_add, name="expense_add"),
    path("expenses/<int:expense_id>/edit/", expense_v7.expense_edit, name="expense_edit"),
    path("expenses/<int:expense_id>/delete/", expense_v7.expense_delete, name="expense_delete"),
    path("receivables/", views.receivables, name="receivables"),
    path("receivables/person/add/", views.receivable_person_add, name="receivable_person_add"),
    path("receivables/<int:person_id>/claim/", views.receivable_claim_add, name="receivable_claim_add"),
    path("receivables/<int:person_id>/repay/", views.receivable_repay, name="receivable_repay"),
    path("receivables/entry/<int:entry_id>/delete/", views.receivable_entry_delete, name="receivable_entry_delete"),
    path("categories/", views.categories, name="categories"),
    path("categories/add/", views.category_add, name="category_add"),
    path("categories/<int:category_id>/toggle/", views.category_toggle, name="category_toggle"),
    path("categories/<int:category_id>/delete/", views.category_delete, name="category_delete"),
    path("reports/", views.reports, name="reports"),
    path("reports/category/<int:category_id>/", category_report_v8.category_report, name="category_report"),
    path("reports/export.xlsx", export_xlsx.financial_export_xlsx, name="financial_export_xlsx"),
]
