import glob
import json
import os

KEYS = [
    "panel.notif_nav_url_global_label",
    "panel.notif_nav_url_global_hint",
    "panel.notif_nav_url_row_placeholder",
]


def test_nav_url_strings_present_in_all_locales():
    base = os.path.join(
        os.path.dirname(__file__),
        "..",
        "custom_components",
        "taskmate",
        "www",
        "locales",
    )
    files = glob.glob(os.path.join(base, "*.json"))
    assert files, "no locale files found"
    for path in files:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for key in KEYS:
            assert key in data and data[key].strip(), f"{key} missing/empty in {os.path.basename(path)}"
