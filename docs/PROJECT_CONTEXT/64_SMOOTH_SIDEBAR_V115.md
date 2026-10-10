# V115 — Smooth SVG sidebar fix
Parent: v114-clean-icon-sidebar-navigation. Nine sidebar Unicode glyphs replaced with inline stroked vector icons. Purchase menu says «خرید تکوین». CSS desktop width-only transition 180ms and pointer-position hysteresis expand at <=72px from right, collapse at >246px from right. Removes delayed timers and conflicting hover handlers. Mobile sidebar remains a drawer. No backend or model changes. This branch is intentionally isolated from other parallel UI branches.

Regression: check_smooth_sidebar_v115
Success marker: SUCCESS: SMOOTH SVG SIDEBAR V115 DEPLOYED
