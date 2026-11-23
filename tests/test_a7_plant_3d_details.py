"""P3-2: the detailed 3D shapes exist exactly for the items whose size is a registry value, and the committed bundle contains them.
Reads the JS source and the built bundle as text; nothing here renders a scene."""
import os
import re
import sys

import test_app_smoke as smoke

sys.path.insert(0, smoke.ROOT)
from python import plant_3d

SRC = open(os.path.join(smoke.ROOT, "web3d", "src", "main.js"), encoding="utf-8").read()
BUNDLE = open(os.path.join(smoke.ROOT, "assets", "plant3d.bundle.js"), encoding="utf-8").read()


def test_detailed_shapes_are_exactly_the_registry_sized_items():
    block = SRC[SRC.index("const DETAIL = {"):SRC.index("const TOP =")]
    ids = set(re.findall(r"'([A-Z]{2}-\d{3})'\(it, g\)", block))
    assert ids == set(plant_3d.DIMENSIONS_FROM_REGISTRY), ids


def test_the_committed_bundle_contains_those_shapes_and_the_camera_hook():
    for item_id in plant_3d.DIMENSIONS_FROM_REGISTRY:
        assert f'"{item_id}"' in BUNDLE or f"'{item_id}'" in BUNDLE or f"{item_id}:" in BUNDLE, item_id
    assert "__PLANT3D_VIEW__" in BUNDLE and "__PLANT3D_READY__" in BUNDLE


def test_the_bundle_makes_no_network_or_eval_calls():
    for bad in ("XMLHttpRequest", "WebSocket", "sendBeacon", "eval(", "new Function"):
        assert bad not in BUNDLE, bad
    # BL-2: the glTF loader library has 3 `fetch(` strings (FileLoader, ImageBitmapLoader). Our own code never calls it: the model
    # is embedded and parsed from memory. (Same rule as tests/test_a9_plant_3d_interaction.py.)
    assert BUNDLE.count("fetch(") <= 3
    for own in (("web3d", "src", "main.js"), ("python", "plant_3d.py")):
        assert "fetch(" not in open(os.path.join(smoke.ROOT, *own), encoding="utf-8").read(), own
