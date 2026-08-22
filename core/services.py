from django.db import transaction
from django.db.models import F
from .models import StockBalance, InventoryMovement

def home_and_total(brand,size,color):
    qs=StockBalance.objects.filter(brand=brand,size=size,color=color)
    home=qs.filter(location__key="home").values_list("qty",flat=True).first() or 0
    total=sum(qs.values_list("qty",flat=True))
    return home,total

@transaction.atomic
def apply_stock_delta(*,brand,size,color,location,delta,movement_type,reference=""):
    bal,_=StockBalance.objects.select_for_update().get_or_create(brand=brand,size=size,color=color,location=location,defaults={"qty":0})
    bal.qty=F("qty")+delta
    bal.save(update_fields=["qty"])
    bal.refresh_from_db()
    InventoryMovement.objects.create(movement_type=movement_type,brand=brand,size=size,color=color,location=location,delta=delta,reference=reference)
    return bal.qty
