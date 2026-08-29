from __future__ import annotations

import re

from .daily_order_import_v8 import _compact_code, _norm_text
from .models import ProductCode


# These aliases describe MODEL TEXT IN THE DIGIKALA TITLE only.
# Seller-code metadata must never be passed to this resolver.
DARMA_TITLE_ALIASES = {
    "d110": "D 110",
    "d220": "D 220",
    "d330": "D 330",
    "d440": "D 440",
    "d550": "D 550",
    "d660": "D 660",
    "pack5": "pack 5",
    "pack05": "pack 5",
    "rah110": "rah-110",
    "rah220": "rah-220",
    "op": "op",
    "opbnw": "op",
    "110": "D 110",
    "220": "D 220",
    "330": "D 330",
    "440": "D 440",
    "550": "D 550",
    "660": "D 660",
    "770": "770",
    "880": "880",
    "990": "990",
    "400": "400",
    "06": "06",
    "6": "06",
    "pack6": "06",
    "p12": "p12",
    "pgw": "pgw",
    "s3": "s3",
}

TAKVIN_TITLE_ALIASES = {
    # Digikala currently writes this title model reversed versus the site's
    # long-standing canonical Takvin code.
    "1654": "654-1",
}


def model_candidate_from_title(title: str) -> str:
    text = _norm_text(title)
    match = re.search(r"مدل\s+(.+?)(?:\s+مجموعه|\s*\|)", text, re.IGNORECASE)
    if not match:
        return ""
    value = match.group(1).strip()
    return re.sub(r"^نخی\s+", "", value, flags=re.IGNORECASE).strip()


def brand_from_title(title: str) -> str:
    text = _norm_text(title)
    if "تکوین" in text:
        return "تکوین"
    if "دارما" in text:
        return "دارما"
    return ""


def resolve_product_from_title(title: str):
    """Resolve a marketplace ProductCode strictly from title text.

    No seller-code value is accepted by this function by design. The title must
    contain both a recognized brand and an explicit model. Unknown/ambiguous
    title models fail closed instead of being guessed.
    """
    brand_name = brand_from_title(title)
    candidate = model_candidate_from_title(title)
    if not brand_name or not candidate:
        return None

    key = _compact_code(candidate)
    aliases = DARMA_TITLE_ALIASES if brand_name == "دارما" else TAKVIN_TITLE_ALIASES
    canonical = aliases.get(key)
    if canonical:
        return ProductCode.objects.filter(
            brand__name=brand_name,
            code=canonical,
            active=True,
        ).first()

    # Exact normalized title-model match inside the title's own brand only.
    matches = [
        product
        for product in ProductCode.objects.select_related("brand").filter(
            brand__name=brand_name,
            active=True,
        )
        if _compact_code(product.code) == key
    ]
    if len(matches) == 1:
        return matches[0]
    return None
