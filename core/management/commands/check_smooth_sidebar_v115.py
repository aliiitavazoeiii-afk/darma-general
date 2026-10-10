"""V115 regression — vector icons, hover hysteresis, correct Takvin label."""
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import get_template


class Command(BaseCommand):
    help = "Validate smooth vector-icon sidebar without touching database."

    def handle(self, *args, **kwargs):
        get_template("base.html")
        html=(Path(settings.BASE_DIR)/"templates/base.html").read_text(encoding="utf-8")
        css=(Path(settings.BASE_DIR)/"static/core/sidebar-v115.css").read_text(encoding="utf-8")
        nav=html.split('<nav class="erp-nav" aria-label="منوی اصلی">',1)[1].split("</nav>",1)[0]
        if nav.count('class="nav114-link') != 9 or nav.count("<svg ") != 9:
            raise RuntimeError("Expected exactly nine accessible SVG navigation icons")
        if "خرید تکوین" not in nav or "خرید تکی" in nav:
            raise RuntimeError("Takvin purchase menu label is not correct")
        for marker in (
            'href="{% url \'dashboard\' %}"',
            'href="{% url \'sale_start\' %}"',
            'href="{% url \'report\' %}"',
            'href="{% url \'inventory\' %}"',
            'href="{% url \'takvin\' %}"',
            'href="{% url \'material_report\' %}"',
            'href="{% url \'digikala\' %}"',
            'href="{% url \'finance\' %}"',
            'href="{% url \'settings_home\' %}"',
        ):
            if marker not in nav:
                raise RuntimeError(f"Sidebar navigation changed: {marker}")
        required=(
            "sidebar-v115.css",
            "distanceFromRight<=72",
            "distanceFromRight>246",
            "transition:width .18s",
            "transition:margin-right .18s",
            "body.sidebar-collapsed .erp-main{margin-right:72px!important}",
        )
        for marker in required:
            if marker not in (html+css):
                raise RuntimeError(f"Smooth sidebar marker missing: {marker}")
        if "main?.addEventListener('mouseenter'" in html or "scheduleHidePeek()" in html:
            raise RuntimeError("Old competing sidebar event/timer listeners remain")
        self.stdout.write("VECTOR NAV ICONS = 9")
        self.stdout.write("TAKVIN LABEL = خرید تکوین")
        self.stdout.write("HOVER HYSTERESIS = 72PX OPEN / 246PX CLOSE")
        self.stdout.write("SIDEBAR WIDTH ANIMATION = 180MS / NO TRANSFORM JUMP")
        self.stdout.write("NO BUSINESS STATE WRITE")
        self.stdout.write(self.style.SUCCESS("SUCCESS: SMOOTH SVG SIDEBAR V115 CHECK PASSED"))
