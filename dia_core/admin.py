from django.contrib import admin

from .models import (
    Account,
    AccountEntry,
    AppSetting,
    Color,
    InventoryAdjustment,
    InventoryMovement,
    Payment,
    Product,
    ProductVariant,
    PurchaseLine,
    Receipt,
    ReturnRecord,
    SaleDay,
    SaleLine,
    Size,
    StockBalance,
    StockLocation,
)


for model in [
    Size, Color, Product, ProductVariant, StockLocation, StockBalance,
    InventoryMovement, SaleDay, SaleLine, PurchaseLine, ReturnRecord,
    InventoryAdjustment, Account, AccountEntry, Payment, Receipt, AppSetting,
]:
    admin.site.register(model)
