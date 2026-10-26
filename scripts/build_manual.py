#!/usr/bin/env python3
"""Bundle the wiki into the integration, for the admin panel's Manual page.

Reads every page in wiki/ and the section order in mkdocs.yml, renders the
markdown with the same extensions the website uses, and writes one JSON file
the panel loads on demand:

  custom_components/taskmate/www/manual/manual.json  (+ manual.json.gz)

The bundle is built, not committed: release-zip.yml runs this before zipping,
so every release carries the wiki exactly as it stood at the tag. Run it by
hand to try the Manual on a dev install.

Screenshots stay on the website — the bundle points <img> tags at GitHub
Pages rather than shipping 24 MB of PNGs in every download.

The HTML goes into the panel with innerHTML, so it is passed through an
allowlist here: only plain document tags and attributes survive, every link
is checked, and the panel's own link attributes are added by this script,
never taken from the page.

Run: python3 scripts/build_manual.py [--out DIR]
     python3 scripts/build_manual.py --check   (CI: build to a temp dir, and
     check every page the panel's "?" buttons open is still there)
Needs: pip install -r requirements-docs.txt  (markdown, pymdown-extensions, pyyaml; pinned from requirements-docs.in)
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import re
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI = REPO_ROOT / "wiki"
MKDOCS = REPO_ROOT / "mkdocs.yml"
MANIFEST = REPO_ROOT / "custom_components" / "taskmate" / "manifest.json"
PANEL = REPO_ROOT / "custom_components" / "taskmate" / "www" / "taskmate-panel.js"
DEFAULT_OUT = REPO_ROOT / "custom_components" / "taskmate" / "www" / "manual"
SITE = "https://tempus2016.github.io/taskmate/"

# Heading ids are prefixed so they cannot collide with anything else on the page.
ID_PREFIX = "tmdoc-"

# The website's markdown_extensions (mkdocs.yml), minus the heading permalinks.
# tests/test_build_manual.py fails if the two lists drift apart.
EXTENSIONS = [
    "admonition",
    "attr_list",
    "tables",
    "toc",
    "pymdownx.superfences",
    "pymdownx.highlight",
    "pymdownx.details",
]


def extension_configs() -> dict:
    from pymdownx.slugs import slugify

    return {
        "toc": {"slugify": slugify(case="lower"), "permalink": False},
        "pymdownx.highlight": {"use_pygments": False},
    }


ALLOWED_TAGS = set(
    "a abbr b blockquote br code dd del details div dl dt em h1 h2 h3 h4 h5 h6 hr i img kbd li"
    " mark ol p pre s small span strong sub summary sup table tbody td tfoot th thead tr u ul".split()
)
VOID_TAGS = {"br", "hr", "img"}
# Dropped together with everything inside them.
DROP_WITH_CONTENT = set("script style iframe object embed noscript template svg math form".split())
ALLOWED_ATTRS = {"class", "id", "title", "alt", "open", "colspan", "rowspan", "align"}
TEXT_ALIGN = re.compile(r"^\s*text-align:\s*(left|right|center)\s*;?\s*$")


class _LooseLoader(yaml.SafeLoader):
    """mkdocs.yml carries a !!python tag for the slugify function; skip it."""


_LooseLoader.add_multi_constructor("tag:yaml.org,2002:python/", lambda loader, suffix, node: None)


def load_mkdocs() -> dict:
    return yaml.load(MKDOCS.read_text(encoding="utf-8"), Loader=_LooseLoader)  # noqa: S506 - SafeLoader subclass


def mkdocs_extension_names(config: dict) -> list[str]:
    return [next(iter(e)) if isinstance(e, dict) else e for e in config.get("markdown_extensions", [])]


def build_nav(items: list) -> list[dict]:
    out = []
    for item in items:
        if isinstance(item, str):
            out.append({"title": item[:-3], "page": item[:-3]})
            continue
        ((title, value),) = item.items()
        if isinstance(value, list):
            out.append({"title": title, "children": build_nav(value)})
        else:
            out.append({"title": title, "page": value[:-3]})
    return out


def nav_pages(nav: list[dict]) -> list[str]:
    pages = []
    for node in nav:
        if "page" in node:
            pages.append(node["page"])
        else:
            pages.extend(nav_pages(node["children"]))
    return pages


def page_url(slug: str, anchor: str = "") -> str:
    url = SITE if slug == "index" else f"{SITE}{slug}/"
    return f"{url}#{anchor}" if anchor else url


class Sanitizer(HTMLParser):
    """Rebuild rendered HTML from an allowlist, rewriting links for the panel."""

    def __init__(self, slug: str, known: set[str]):
        super().__init__(convert_charrefs=True)
        self.slug = slug
        self.known = known
        self.out: list[str] = []
        self.open: list[str] = []
        self.drop_depth = 0

    def _link(self, href: str) -> dict[str, str]:
        href = href.strip()
        if re.match(r"^(https?:|mailto:)", href, re.I):
            return {"href": href, "target": "_blank", "rel": "noopener noreferrer"}
        if href.startswith("#"):
            anchor = href[1:]
            return {
                "href": page_url(self.slug, anchor),
                "data-act": "man-go",
                "data-doc": self.slug,
                "data-anchor": anchor,
            }
        m = re.match(r"^(?:\./)?([^#?:/]+)\.md(?:#(.*))?$", href)
        if m and unquote(m.group(1)) in self.known:
            doc, anchor = unquote(m.group(1)), m.group(2) or ""
            return {"href": page_url(doc, anchor), "data-act": "man-go", "data-doc": doc, "data-anchor": anchor}
        if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I):
            return {}  # javascript:, data: and friends
        # Anything else relative (an image, a page outside the nav): the website has it.
        target = SITE + re.sub(r"\.md(?=$|#)", "/", href.lstrip("./"))
        return {"href": target, "target": "_blank", "rel": "noopener noreferrer"}

    def _attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        kept: dict[str, str] = {}
        for name, value in attrs:
            name = name.lower()
            value = value or ""
            if name in ALLOWED_ATTRS:
                kept[name] = ID_PREFIX + value if name == "id" else value
            elif name == "style" and TEXT_ALIGN.match(value):
                kept["style"] = value.strip()
            elif tag == "a" and name == "href":
                kept.update(self._link(value))
            elif tag == "img" and name == "src":
                src = self._image_src(value)
                if src:
                    kept["src"] = src
        if tag == "img":
            kept["loading"] = "lazy"
        return kept

    @staticmethod
    def _image_src(value: str) -> str:
        """Where a picture may load from: the docs site, and nothing else.

        Every admin panel that opens the Manual fetches every <img> in it, so a
        wiki page pointing one at another host would hand that host every
        reader's address. Relative paths (the screenshots in wiki/images/) are
        rewritten onto the site; a URL already on the site is kept; anything
        else — another https host, http, a bare //host, /rooted, data:, a
        scheme — is dropped, and the <img> with it.
        """
        src = value.strip()
        if src.startswith(SITE):
            return src
        if re.match(r"^(?:\.{1,2}/)*[^/:#?][^:]*$", src):
            return SITE + src.lstrip("./")
        return ""

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in DROP_WITH_CONTENT:
            if tag not in VOID_TAGS:
                self.drop_depth += 1
            return
        if self.drop_depth or tag not in ALLOWED_TAGS:
            return
        kept = self._attrs(tag, attrs)
        if tag == "img" and "src" not in kept:
            return  # no picture, or one from a host the Manual does not load from
        rendered = "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in kept.items())
        self.out.append(f"<{tag}{rendered}>")
        if tag not in VOID_TAGS:
            self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_TAGS and self.open and self.open[-1] == tag.lower():
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in DROP_WITH_CONTENT:
            self.drop_depth = max(0, self.drop_depth - 1)
            return
        if self.drop_depth or tag not in ALLOWED_TAGS or tag in VOID_TAGS or tag not in self.open:
            return
        while self.open:
            top = self.open.pop()
            self.out.append(f"</{top}>")
            if top == tag:
                break

    def handle_data(self, data):
        if not self.drop_depth:
            self.out.append(html.escape(data, quote=False))

    def result(self) -> str:
        self.close()
        return "".join(self.out) + "".join(f"</{t}>" for t in reversed(self.open))


def sanitize(rendered: str, slug: str, known: set[str]) -> str:
    s = Sanitizer(slug, known)
    s.feed(rendered)
    return s.result()


def render_page(src: str, slug: str, known: set[str]) -> dict:
    import markdown

    md = markdown.Markdown(extensions=EXTENSIONS, extension_configs=extension_configs())
    body = md.convert(src)
    title_m = re.search(r"^#\s+(.+?)\s*#*\s*$", src, re.M)
    toc = []
    for top in md.toc_tokens:
        for tok in top["children"] if top["level"] == 1 else [top]:
            if tok["level"] == 2:
                toc.append({"id": ID_PREFIX + tok["id"], "text": html.unescape(re.sub(r"<[^>]+>", "", tok["name"]))})
    return {
        "title": html.unescape(re.sub(r"[*_`]", "", title_m.group(1))) if title_m else slug.replace("-", " "),
        "html": sanitize(body, slug, known),
        "toc": toc,
    }


def build(out_dir: Path) -> dict:
    config = load_mkdocs()
    nav = build_nav(config["nav"])
    in_nav = nav_pages(nav)
    files = {p.stem: p for p in sorted(WIKI.glob("*.md"))}
    missing = [p for p in in_nav if p not in files]
    if missing:
        raise SystemExit(f"mkdocs.yml nav names pages that are not in wiki/: {', '.join(missing)}")
    known = set(files)
    pages = {slug: render_page(path.read_text(encoding="utf-8"), slug, known) for slug, path in files.items()}
    version = json.loads(MANIFEST.read_text(encoding="utf-8")).get("version", "")
    bundle = {"version": version, "site": SITE, "nav": nav, "pages": pages}

    out_dir.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    (out_dir / "manual.json").write_bytes(raw)
    (out_dir / "manual.json.gz").write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    return bundle


def panel_help_targets() -> dict[str, tuple[str, str]]:
    """The MANUAL_HELP map in the panel: admin page -> (wiki page, heading id)."""
    src = PANEL.read_text(encoding="utf-8")
    block = re.search(r"const MANUAL_HELP = \{(.*?)\n\};", src, re.S)
    if not block:
        raise SystemExit("MANUAL_HELP not found in taskmate-panel.js")
    return {
        tab: (doc, anchor or "")
        for tab, doc, anchor in re.findall(r'^\s*(\w+):\s*\["([^"]+)"(?:,\s*"([^"]*)")?\]', block.group(1), re.M)
    }


def check(bundle: dict) -> list[str]:
    problems = []
    config = load_mkdocs()
    names = mkdocs_extension_names(config)
    if names != EXTENSIONS:
        problems.append(f"markdown extensions differ from mkdocs.yml: {names} vs {EXTENSIONS}")
    targets = panel_help_targets()
    if not targets:
        problems.append("MANUAL_HELP in taskmate-panel.js is empty")
    for tab, (doc, anchor) in targets.items():
        page = bundle["pages"].get(doc)
        if page is None:
            problems.append(f'"?" on {tab} opens {doc}.md, which is not in wiki/')
        elif anchor and f'id="{ID_PREFIX}{anchor}"' not in page["html"]:
            problems.append(f'"?" on {tab} opens {doc}.md#{anchor}, but that heading is gone')
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    parser.add_argument("--check", action="store_true", help="build to a temp dir and check the panel's links")
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = build(Path(tmp))
        problems = check(bundle)
        for problem in problems:
            print(f"FAIL {problem}")
        if problems:
            return 1
        print(f'PASS — {len(bundle["pages"])} pages bundle cleanly; every "?" in the panel opens a real page.')
        return 0
    bundle = build(args.out)
    size = (args.out / "manual.json").stat().st_size
    gz = (args.out / "manual.json.gz").stat().st_size
    print(f"Manual: {len(bundle['pages'])} pages, {size // 1024} KB ({gz // 1024} KB gzipped) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
