"""P3-4: the 3D tab's interaction (Fit view / Focus buttons, click card, group-order arrows). Reads the JS source and the built bundle as text;
nothing here renders a scene (the behaviour was checked once in headless Chromium, see the PR)."""
import os
import re
import sys

import test_app_smoke as smoke

sys.path.insert(0, smoke.ROOT)
from python import plant_3d

SRC = open(os.path.join(smoke.ROOT, "web3d", "src", "main.js"), encoding="utf-8").read()
BUNDLE = open(os.path.join(smoke.ROOT, "assets", "plant3d.bundle.js"), encoding="utf-8").read()


def test_focus_buttons_come_from_the_group_list_and_fit_view_exists():
    assert "for (const g of D.order) btn(D.groups[g]" in SRC
    assert "btn('Fit view'" in SRC and "Fit view" in BUNDLE
    assert len(plant_3d.GROUP_ORDER) == len(plant_3d.GROUP_NAMES) == 7


def test_the_card_escapes_every_registry_text_it_prints():
    card = SRC[SRC.index("card.innerHTML = `"):SRC.index("card.style.display = 'block'")]
    interpolated = re.findall(r"\$\{([^}]*)\}", card)
    raw = [e for e in interpolated if not e.startswith("esc(") and "STATE_COLOR" not in e and "u.count" not in e
           and "u.basis ===" not in e]
    assert raw == [], raw


def test_the_arrows_are_only_the_group_order_not_a_stream_path():
    block = SRC[SRC.index("// flow arrows between the group rows"):SRC.index("let selected = null;")]
    assert "['FE', 'GA', 'GC', 'HB']" in block and "ORDER OF THE GROUPS ONLY" in block


def test_a_drag_is_not_a_click_and_the_bundle_stays_offline():
    assert "Math.hypot(e.clientX - down[0]" in SRC and "pointerup" in BUNDLE
    for bad in ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "eval(", "new Function"):
        assert bad not in BUNDLE, bad
