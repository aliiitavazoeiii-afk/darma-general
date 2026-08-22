from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models


class Brand(models.Model):
    name = models.CharField(max_length=50, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Size(models.Model):
    name = models.CharField(max_length=20, unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["sort_order", "id"]


class Color(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=10, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ProductCode(models.Model):
    code = models.CharField(max_length=50)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products")
    pack_qty = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["brand", "code"], name="uniq_brand_code")]

    def __str__(self):
        return f"{self.brand} - {self.code}"


class ProductComposition(models.Model):
    product = models.ForeignKey(ProductCode, on_delete=models.CASCADE, related_name="composition")
    color = models.ForeignKey(Color, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "color"], name="uniq_product_color")]


class ProductSize(models.Model):
    product = models.ForeignKey(ProductCode, on_delete=models.CASCADE, related_name="sizes")
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    default_sale_price = models.PositiveBigIntegerField(default=0)
    unit_cost = models.PositiveBigIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "size"], name="uniq_product_size")]


class StockLocation(models.Model):
    HOME = "home"
    KHORSHID = "khorshid"
    key = models.CharField(max_length=20, choices=[(HOME, "خانه"), (KHORSHID, "خورشید")], unique=True)
    title = models.CharField(max_length=50)

    def __str__(self):
        return self.title


class StockBalance(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT)
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    color = models.ForeignKey(Color, on_delete=models.PROTECT)
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT)
    qty = models.IntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["brand", "size", "color", "location"], name="uniq_stock_balance")]


class StockThreshold(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT)
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    color = models.ForeignKey(Color, on_delete=models.PROTECT)
    home_min = models.PositiveIntegerField(default=0)
    total_min = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["brand", "size", "color"], name="uniq_stock_threshold")]


class SaleDay(models.Model):
    date = models.DateField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.date)


class SaleLine(models.Model):
    day = models.ForeignKey(SaleDay, on_delete=models.CASCADE, related_name="lines")
    product_size = models.ForeignKey(ProductSize, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=0)
    inventory_applied_quantity = models.PositiveIntegerField(default=0)
    sale_price = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["day", "product_size"], name="uniq_day_product_size")]

    @property
    def gross_sales(self):
        return self.quantity * self.sale_price

    @property
    def shorts_count(self):
        return self.quantity * self.product_size.product.pack_qty


class Replacement(models.Model):
    sale_line = models.ForeignKey(SaleLine, on_delete=models.CASCADE, related_name="replacements")
    source_color = models.ForeignKey(Color, on_delete=models.PROTECT, related_name="replacement_sources")
    target_color = models.ForeignKey(Color, on_delete=models.PROTECT, null=True, blank=True, related_name="replacement_targets")
    qty = models.PositiveIntegerField()


class InventoryMovement(models.Model):
    PURCHASE = "purchase"
    SALE = "sale"
    TRANSFER = "transfer"
    PRODUCTION = "production"
    ADJUST = "adjust"
    movement_type = models.CharField(max_length=20, choices=[(PURCHASE, "خرید"), (SALE, "فروش"), (TRANSFER, "انتقال"), (PRODUCTION, "تولید"), (ADJUST, "اصلاح")])
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT)
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    color = models.ForeignKey(Color, on_delete=models.PROTECT)
    location = models.ForeignKey(StockLocation, on_delete=models.PROTECT)
    delta = models.IntegerField()
    reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AppSetting(models.Model):
    key = models.CharField(max_length=80, unique=True)
    value = models.CharField(max_length=200)
    label = models.CharField(max_length=120)
    updated_at = models.DateTimeField(auto_now=True)


class Account(models.Model):
    MELAT = "melat"
    MOFID = "mofid"
    DIGIKALA = "digikala"
    PEDRAM = "pedram"
    TAKVIN = "takvin"
    key = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=100)
    opening_balance = models.BigIntegerField(default=0)

    def __str__(self):
        return self.title


class MoneyMovement(models.Model):
    TRANSFER = "transfer"
    EXPENSE = "expense"
    SETTLEMENT = "settlement"
    PURCHASE = "purchase"
    RECEIPT = "receipt"
    date = models.DateField()
    kind = models.CharField(max_length=30, choices=[(TRANSFER, "انتقال"), (EXPENSE, "خرج"), (SETTLEMENT, "تسویه"), (PURCHASE, "خرید"), (RECEIPT, "دریافت")])
    amount = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])
    from_account = models.ForeignKey(Account, on_delete=models.PROTECT, null=True, blank=True, related_name="out_movements")
    to_account = models.ForeignKey(Account, on_delete=models.PROTECT, null=True, blank=True, related_name="in_movements")
    title = models.CharField(max_length=150)
    affects_capital = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
