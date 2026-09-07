from django.db import models


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, allow_unicode=True)
    accent = models.CharField(max_length=24, default="green")
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "دسته هزینه"
        verbose_name_plural = "دسته‌های هزینه"

    def __str__(self):
        return self.name


class DailyExpense(models.Model):
    date = models.DateField(db_index=True)
    amount = models.BigIntegerField()
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    title = models.CharField(max_length=160, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date", "-created_at", "-id")
        indexes = [
            models.Index(fields=("date", "category"), name="exp_date_category_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="expense_amount_positive",
            ),
        ]
        verbose_name = "هزینه"
        verbose_name_plural = "هزینه‌ها"

    def __str__(self):
        return f"{self.date} - {self.amount}"


class ReceivablePerson(models.Model):
    name = models.CharField(max_length=120, unique=True)
    note = models.CharField(max_length=250, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name", "id")
        verbose_name = "شخص بدهکار"
        verbose_name_plural = "اشخاص بدهکار"

    def __str__(self):
        return self.name


class ReceivableEntry(models.Model):
    CLAIM = "claim"
    PAYMENT = "payment"
    KIND_CHOICES = (
        (CLAIM, "طلب"),
        (PAYMENT, "تسویه"),
    )

    person = models.ForeignKey(
        ReceivablePerson,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    date = models.DateField(db_index=True)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES)
    amount = models.BigIntegerField()
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-date", "-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="receivable_amount_positive",
            ),
        ]
        indexes = [
            models.Index(fields=("person", "kind"), name="recv_person_kind_idx"),
        ]
        verbose_name = "گردش طلب"
        verbose_name_plural = "گردش طلب‌ها"

    def __str__(self):
        return f"{self.person} - {self.get_kind_display()} - {self.amount}"
