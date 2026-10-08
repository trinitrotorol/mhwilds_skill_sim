"""Release HTML must remain usable, distinct, crawlable and CSP compatible."""

from dataclasses import replace
import hashlib
from html.parser import HTMLParser
from pathlib import Path

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
    # The canonical apps no longer generate a migration notice, even when CSS/JS fail.
    assert not page.attributes("aside")
    assert "service-migration-title" not in html
    assert "以前のサイトで所持品を登録した方へ" not in html
    assert "?legacy=1" not in html
    assert f"{script.ROOT_ORIGIN}/game-guide/mhwilds-guide/" in links
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
    assert "Recover inventory saved on the old site" in html
    assert "not transferred automatically" in html
    assert page.attributes("aside", **{"aria-labelledby": "service-migration-title"})
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


@pytest.mark.parametrize("app_path", [*script.PAGES, *script.LEGACY_PATHS])
def test_translations_share_landmarks_ids_links_and_default_to_japanese(app_path):
    html = script.enrich_html(SHELL, app_path, f"/{app_path}/assets/context.css")
    page = Page(html)
    canonical_path = script.LEGACY_PATHS.get(app_path, app_path)
    english = script.ENGLISH_PAGES[canonical_path]
    assert page.attributes("html")[0]["lang"] == "ja"
    japanese_spans = page.attributes("span", **{"data-service-lang": "ja"})
    english_spans = page.attributes("span", **{"data-service-lang": "en"})
    assert len(japanese_spans) == len(english_spans) > 15
    assert all(attrs["lang"] == "ja" for attrs in japanese_spans)
    assert all(attrs["lang"] == "en" for attrs in english_spans)
    ids = [attrs["id"] for _, attrs in page.tags if "id" in attrs]
    assert len(ids) == len(set(ids))
    # Hiding a translation cannot leave duplicate headings, landmarks or links.
    assert len(page.attributes("h1")) == len(page.attributes("main")) == 1
    assert len(page.attributes("section", id="service-overview")) == 1
    assert len(page.attributes("h2", id="service-overview-title")) == 1
    assert english.introduction in [value for _, value in page.text]
    assert english.limitation in [value for _, value in page.text]
    description = page.attributes("meta", name="description")[0]
    assert description["data-service-content-en"] == english.description
    assert description["data-service-content-ja"] == description["content"]
    assert page.attributes("title")[0]["data-service-text-en"] == english.title
    assert (
        page.attributes("meta", property="og:title")[0]["data-service-content-en"]
        == english.title
    )
    assert (
        page.attributes("meta", property="og:locale")[0]["data-service-content-en"]
        == "en_US"
    )
    assert all(
        "data-service-aria-label-en" in attrs for attrs in page.attributes("nav")
    )
    stylesheet = Path(script.__file__).with_name("service-html.css").read_text()
    assert 'html:not([lang="en"]) [data-service-lang="en"]' in stylesheet
    assert 'html[lang="en"] [data-service-lang="ja"]' in stylesheet
    assert "display: none !important;" in stylesheet


def test_english_editorial_text_cannot_inject_markup_or_attributes(monkeypatch):
    payload = '"><script src="https://evil.invalid/en.js"></script>&'
    english = replace(
        script.ENGLISH_PAGES[script.SIM_PATH],
        title=payload,
        description=payload,
        introduction=payload,
    )
    monkeypatch.setitem(script.ENGLISH_PAGES, script.SIM_PATH, english)
    page = Page(
        script.enrich_html(SHELL, script.SIM_PATH, "/skill-sim/assets/info.css")
    )
    assert page.attributes("script") == Page(SHELL).attributes("script")
    assert (
        page.attributes("meta", name="description")[0]["data-service-content-en"]
        == payload
    )
    assert payload in [value for _, value in page.text]


def test_release_copies_a_hashed_same_origin_locale_module_for_every_app(tmp_path):
    module = Path(script.__file__).with_name("service-locale.mjs").read_bytes()
    name = f"service-locale-{hashlib.sha256(module).hexdigest()[:16]}.js"
    for app_path in [*script.PAGES, *script.LEGACY_PATHS]:
        directory = tmp_path / app_path
        directory.mkdir(parents=True)
        (directory / "index.html").write_text(SHELL)
    script.enrich_release_apps(tmp_path)
    for app_path in [*script.PAGES, *script.LEGACY_PATHS]:
        directory = tmp_path / app_path
        page = Page((directory / "index.html").read_text())
        assert (directory / "assets" / name).read_bytes() == module
        assert page.attributes("script") == [
            *Page(SHELL).attributes("script"),
            {"type": "module", "src": f"/{app_path}/assets/{name}"},
        ]
        assert not page.attributes("style")
        assert not any(key.startswith("on") for _, attrs in page.tags for key in attrs)


@pytest.mark.parametrize(
    "module",
    ["https://other.invalid/a.js", "//other.invalid/a.js", '/skill-sim/assets/x" y="z'],
)
def test_external_or_unscoped_locale_modules_are_rejected(module):
    with pytest.raises(ValueError, match="assets path"):
        script.enrich_html(
            SHELL, script.SIM_PATH, "/skill-sim/assets/context.css", module
        )
