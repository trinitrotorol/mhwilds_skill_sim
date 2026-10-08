"""Release HTML must remain usable, distinct, crawlable and CSP compatible."""

from dataclasses import replace
from html.parser import HTMLParser

import pytest

from scripts import service_html as script

SHELL = """<!doctype html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Old title</title><meta NAME="DESCRIPTION" content="old">
<link rel="canonical" href="https://wrong.example/">
<meta property="og:url" content="https://wrong.example/">
<script type="module" crossorigin src="/assets/application.js"></script>
<link rel="stylesheet" crossorigin href="/assets/application.css">
</head><body><div id="root"></div></body></html>"""


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.tags = []
        self.context = []
        self.stack = []
        self.text = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        self.context.append((tag, tuple(self.stack)))
        if tag not in {"meta", "link", "br", "input"}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.stack:
            self.stack = self.stack[: self.stack.index(tag)]

    def handle_data(self, data):
        if data.strip():
            self.text.append((tuple(self.stack), data))

    def attributes(self, tag, **matching):
        return [
            attrs
            for actual, attrs in self.tags
            if actual == tag and all(attrs.get(k) == v for k, v in matching.items())
        ]


@pytest.mark.parametrize("app_path", [script.SIM_PATH, script.CHECKER_PATH])
def test_each_app_has_unique_canonical_metadata_and_visible_useful_copy(app_path):
    html = script.enrich_html(SHELL, app_path, f"/{app_path}/assets/context.css")
    page = Page(html)
    canonical = f"https://mhwilds.trinitrotorol.com/{app_path}/"
    assert page.attributes("link", rel="canonical") == [
        {"rel": "canonical", "href": canonical}
    ]
    assert page.attributes("meta", property="og:url") == [
        {"property": "og:url", "content": canonical}
    ]
    assert len(page.attributes("meta", name="description")) == 1
    assert page.attributes("meta", name="description")[0]["content"] == (
        script.PAGES[app_path].description
    )
    title = [value for ancestors, value in page.text if "title" in ancestors]
    assert title == [script.PAGES[app_path].title]
    assert (
        script.PAGES[script.SIM_PATH].title != script.PAGES[script.CHECKER_PATH].title
    )
    assert script.PAGES[script.SIM_PATH].description != (
        script.PAGES[script.CHECKER_PATH].description
    )
    assert "wrong.example" not in html
    # Useful copy is not restricted to noscript or hidden from ordinary visitors.
    visible = [value for ancestors, value in page.text if "section" in ancestors]
    assert script.PAGES[app_path].introduction in visible
    assert script.PAGES[app_path].limitation in visible
    assert not page.attributes("section", hidden="")
    assert not page.attributes("section", **{"aria-hidden": "true"})
    assert len(page.attributes("h1")) == 1
    assert len(page.attributes("main")) == 1
    assert all(
        "noscript" in ancestors
        for tag, ancestors in page.context
        if tag in {"h1", "main"}
    )
    assert page.attributes("div", id="root") == [{"id": "root"}]
    links = {attrs["href"] for attrs in page.attributes("a")}
    assert {url for url, _ in script.SITE_LINKS} <= links
    assert f"/{script.PAGES[app_path].related_path}/" in links
    assert all(
        url.startswith(("/", "#", f"{script.ROOT_ORIGIN}/"))
        and not url.startswith("//")
        for url in links
    )
    assert any("JavaScript" in value for _, value in page.text)
    assert page.attributes("aside", **{"aria-labelledby": "service-migration-title"})
    assert f"{script.ROOT_ORIGIN}/{script.LEGACY_CHECKER_PATH}/?legacy=1" in links
    assert not page.attributes("meta", name="robots")


@pytest.mark.parametrize("old_path,new_path", script.LEGACY_PATHS.items())
def test_legacy_export_shell_retains_old_assets_but_points_canonical_to_new_site(
    old_path, new_path
):
    html = script.enrich_html(SHELL, old_path, f"/{old_path}/assets/context.css")
    page = Page(html)
    assert page.attributes("link", rel="canonical")[0]["href"] == (
        f"{script.ORIGIN}/{new_path}/"
    )
    assert page.attributes("meta", name="robots")[0]["content"] == "noindex,follow"
    other_old_path = next(path for path in script.LEGACY_PATHS if path != old_path)
    links = {attrs["href"] for attrs in page.attributes("a")}
    assert f"/{other_old_path}/?legacy=1" in links
    assert f"{script.ORIGIN}/{script.CHECKER_PATH}/" in links
    assert page.attributes("link", href=f"/{old_path}/assets/context.css")
    assert "保存データは残っています" in html
    assert page.attributes("script") == Page(SHELL).attributes("script")


def test_built_module_and_existing_assets_survive_without_relaxing_csp():
    inline = '<script>const text = "</head>";</script>'
    original = SHELL.replace("</head>", inline + "</head>")
    html = script.enrich_html(
        original, script.SIM_PATH, f"/{script.SIM_PATH}/assets/context.css"
    )
    page = Page(html)
    assert inline in html
    assert page.attributes("script") == Page(original).attributes("script")
    assert page.attributes("link", href="/assets/application.css")
    assert not page.attributes("style")
    assert not any("style" in attrs for _, attrs in page.tags)
    assert not any(key.startswith("on") for _, attrs in page.tags for key in attrs)
    assert not any(
        attrs.get("src", "").startswith(("https:", "http:", "//"))
        for _, attrs in page.tags
    )


def test_editorial_text_is_escaped_in_metadata_and_visible_copy(monkeypatch):
    payload = '"><script src="https://evil.invalid/x.js"></script>&'
    original = script.PAGES[script.CHECKER_PATH]
    page_config = replace(
        original,
        title=payload,
        description=payload,
        introduction=payload,
        steps=(payload,),
    )
    monkeypatch.setitem(script.PAGES, script.CHECKER_PATH, page_config)
    html = script.enrich_html(
        SHELL, script.CHECKER_PATH, f"/{script.CHECKER_PATH}/assets/context.css"
    )
    page = Page(html)
    assert page.attributes("script") == Page(SHELL).attributes("script")
    assert page.attributes("meta", name="description")[0]["content"] == payload
    assert payload in [
        value for ancestors, value in page.text if "section" in ancestors
    ]
    assert not page.attributes("script", src="https://evil.invalid/x.js")


@pytest.mark.parametrize(
    "stylesheet", ["https://other.invalid/a.css", "//other.invalid/a.css", '/x" y="z']
)
def test_external_or_unscoped_stylesheets_are_rejected(stylesheet):
    with pytest.raises(ValueError, match="assets path"):
        script.enrich_html(SHELL, script.SIM_PATH, stylesheet)


@pytest.mark.parametrize("source", ["built", SHELL.replace("</head>", "")])
def test_incomplete_build_output_is_rejected_before_publication(source):
    with pytest.raises(ValueError, match="complete"):
        script.enrich_html(source, script.SIM_PATH, f"/{script.SIM_PATH}/assets/a.css")


def test_accidental_second_enrichment_cannot_duplicate_navigation_or_metadata():
    url = f"/{script.SIM_PATH}/assets/context.css"
    html = script.enrich_html(SHELL, script.SIM_PATH, url)
    with pytest.raises(ValueError, match="unenriched"):
        script.enrich_html(html, script.SIM_PATH, url)
