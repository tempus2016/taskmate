"""Printable reward voucher: an approved reward as a slip of paper to hand over.

Like the weekly chart in ``printable.py``: a self-contained HTML page with no
external assets, built by pure string formatting with no HA imports so it is
unit-testable. The panel asks for it over an admin-only WebSocket command and
may pass its own translated labels; every value that reaches the page is
HTML-escaped.
"""

from __future__ import annotations

from html import escape

DEFAULT_LABELS = {
    "title": "Voucher",
    "for": "For: {name}",
    "from": "A present from {name}",
    "earned": "Earned with {points} {points_name} · {date}",
    "signed": "Signed:",
}
LABEL_KEYS = tuple(DEFAULT_LABELS)
LABEL_MAX = 120


def _fill(template: str, values: dict[str, str]) -> str:
    """Swap the known ``{placeholders}`` — no str.format on caller text."""
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", value)
    return out


def build_voucher(
    *,
    reward_name: str,
    child_name: str,
    cost: int,
    date_text: str,
    points_name: str = "Stars",
    buyer_name: str = "",
    labels: dict[str, str] | None = None,
) -> str:
    """Render one voucher as a standalone HTML document."""
    text = {**DEFAULT_LABELS, **{k: v for k, v in (labels or {}).items() if k in LABEL_KEYS and v}}
    title = escape(text["title"])
    who = escape(_fill(text["for"], {"name": child_name}))
    earned = escape(_fill(text["earned"], {"points": str(int(cost)), "points_name": points_name, "date": date_text}))
    gift = f'<p class="gift">{escape(_fill(text["from"], {"name": buyer_name}))}</p>' if buyer_name else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} — {escape(reward_name)}</title>
<style>
  @page {{ size: A5 landscape; margin: 10mm; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 16px;
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    color: #000; background: #fff;
  }}
  /* A dashed edge to cut along: the point is a thing to hold. */
  .voucher {{
    border: 2.5px dashed #000; border-radius: 14px;
    padding: 22px 26px; max-width: 640px; margin: 0 auto;
  }}
  .kicker {{ font-size: 13px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }}
  h1 {{ font-size: 30px; margin: 8px 0 14px; line-height: 1.15; }}
  .for {{ font-size: 18px; font-weight: 700; margin: 0 0 4px; }}
  .gift {{ font-size: 14px; margin: 0 0 4px; }}
  .earned {{ font-size: 14px; color: #333; margin: 0; }}
  .sign {{ display: flex; align-items: flex-end; gap: 10px; margin-top: 30px; font-size: 15px; }}
  .line {{ flex: 1; border-bottom: 1.5px solid #000; height: 22px; }}
  @media print {{ body {{ padding: 0; }} }}
</style>
</head>
<body>
<div class="voucher">
  <div class="kicker">🎁 {title}</div>
  <h1>{escape(reward_name)}</h1>
  <p class="for">{who}</p>
  {gift}
  <p class="earned">{earned}</p>
  <div class="sign"><span>{escape(text["signed"])}</span><span class="line"></span></div>
</div>
</body>
</html>"""
