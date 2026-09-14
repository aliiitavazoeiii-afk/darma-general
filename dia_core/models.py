from django.core.validators import MinValueValidator
from django.db import models


class Size(models.Model):
    name = models.CharField(max_length=30, unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class Color(models.Model):
    name = models.CharField(max_length=60, unique=True)
    code = models.CharField(max_length=20, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Product(models.Model):
    code = models.CharField(max_length=60, unique=True)
    title = models.CharField(max_length=140, blank=True)
    active = models.BooleanField(default=True)
    note = models.CharField(max_length=250, blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.title or self.code


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    color = models.ForeignKey(Color, on_delete=models.PROTECT)
    default_sale_price = models.PositiveBigIntegerField(default=0)
    unit_cost = models.PositiveBigIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "size", "color"], name="uniq_dia_product_variant")
        ]
        ordering = ["product__code", "size__sort_order", "color__name"]

    def __str__(self):
        return f"{self.product.code} / {self.size.name} / {self.color.name}"


class StockLocation(models.Model):
    key = models.SlugField(max_length=30, unique=True)
    title = models.CharField(max_length=80)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.title


class StockBalance(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="stock_balances")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT, related_name="stock_balances")
    qty = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["variant", "location"], name="uniq_dia_variant_location")
        ]


class InventoryMovement(models.Model):
    PURCHASE = "purchase"
    SALE = "sale"
    RETURN = "return"
    ADJUST = "adjust"
    MOVEMENT_CHOICES = [
        (PURCHASE, "خرید"),
        (SALE, "فروش"),
        (RETURN, "مرجوعی"),
        (ADJUST, "اصلاح"),
    ]

    date = models.DateField(db_index=True)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_CHOICES, db_index=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT)
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT)
    delta = models.IntegerField()
    reference = models.CharField(max_length=140, blank=True, db_index=True)
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class SaleDay(models.Model):
    date = models.DateField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return str(self.date)


class SaleLine(models.Model):
    day = models.ForeignKey(SaleDay, on_delete=models.CASCADE, related_name="lines")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="sale_lines")
    quantity = models.PositiveIntegerField(default=0)
    inventory_applied_quantity = models.PositiveIntegerField(default=0)
    sale_price = models.PositiveBigIntegerField(default=0)
    unit_cost_snapshot = models.PositiveBigIntegerField(default=0)
    digikala_fee_unit = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["day", "variant"], name="uniq_dia_day_variant")
        ]
        ordering = ["variant__product__code", "variant__size__sort_order", "variant__color__name"]

    @property
    def gross_sales(self):
        return int(self.quantity or 0) * int(self.sale_price or 0)


class PurchaseLine(models.Model):
    date = models.DateField(db_index=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="purchase_lines")
    quantity = models.PositiveIntegerField(default=0)
    inventory_applied_quantity = models.PositiveIntegerField(default=0)
    unit_cost = models.PositiveBigIntegerField(default=0)
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["date", "variant"], name="uniq_dia_purchase_date_variant")
        ]
        ordering = ["-date", "variant__product__code"]


class ReturnRecord(models.Model):
    date = models.DateField(db_index=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="returns")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]


class InventoryAdjustment(models.Model):
    date = models.DateField(db_index=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="adjustments")
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT)
    delta = models.IntegerField()
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]


class Account(models.Model):
    title = models.CharField(max_length=100, unique=True)
    opening_balance = models.BigIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class AccountEntry(models.Model):
    date = models.DateField(db_index=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="entries")
    delta = models.BigIntegerField()
    title = models.CharField(max_length=180)
    reference = models.CharField(max_length=140, blank=True, db_index=True)
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]


class Payment(models.Model):
    date = models.DateField(db_index=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="payments")
    amount = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])
    title = models.CharField(max_length=160)
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]


class Receipt(models.Model):
    date = models.DateField(db_index=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="receipts")
    amount = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])
    title = models.CharField(max_length=160)
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]


class AppSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=200)
    label = models.CharField(max_length=160)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.label
