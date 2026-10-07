"""Visible, crawlable context for the two static applications in a release."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path

ORIGIN = "https://trinitrotorol.com"
SIM_PATH = "game-guide/mhwilds-skill-sim"
CHECKER_PATH = "game-guide/mhwilds-inventory-checker"


@dataclass(frozen=True)
class ServicePage:
    title: str
    description: str
    heading: str
    introduction: str
    steps: tuple[str, ...]
    limitation: str
    related_path: str
    related_label: str


PAGES = {
    SIM_PATH: ServicePage(
        title="モンハンワイルズ スキルシミュレーター｜装備・スキル検索 | trinitrotorol",
        description=(
            "モンスターハンターワイルズのスキル条件から装備候補を検索。"
            "所持装飾品・固定護石・鑑定護石を反映し、スキルとスロットの組み合わせを"
            "ブラウザで確認できる非公式ツールです。"
        ),
        heading="スキル条件から、手持ちに合う装備を探す",
        introduction=(
            "モンスターハンターワイルズで発動させたいスキルとレベルを指定し、"
            "武器・防具・護石・装飾品の組み合わせを調べるスキルシミュレーターです。"
            "装備選びの候補を比較するための非公式ツールとして利用できます。"
        ),
        steps=(
            "必要な武器・防具スキルやシリーズ・グループスキルを選び、検索条件を設定します。",
            "手持ちで組みたい場合は所持品チェッカーで装飾品と護石を登録し、所持情報を利用する検索を選びます。",
            "検索結果の装備、発動スキル、装飾品の配置を確認します。候補が見つからない場合は条件を減らして再検索します。",
        ),
        limitation=(
            "検索はブラウザ内で実行します。条件や端末によって時間がかかり、"
            "時間などの上限に達すると、探索済みの候補を部分結果として表示することがあります。"
            "手動で中断した場合は結果を表示しません。"
            "候補なし・中断・探索完了の表示を区別して確認してください。"
            "ゲームの更新によってデータと実際の仕様に差が生じる場合があります。"
        ),
        related_path=CHECKER_PATH,
        related_label="所持品チェッカーで装飾品・護石を登録する",
    ),
    CHECKER_PATH: ServicePage(
        title="モンハンワイルズ 所持品チェッカー｜装飾品・護石を管理 | trinitrotorol",
        description=(
            "モンスターハンターワイルズの装飾品・固定護石・鑑定護石の所持数を管理。"
            "ブラウザ内に保存し、JSONでバックアップ。"
            "同じサイトのスキルシミュレーターで手持ちを反映できます。"
        ),
        heading="装飾品と護石を整理して、装備検索に使う",
        introduction=(
            "モンスターハンターワイルズの装飾品・固定護石の所持数と、"
            "鑑定護石ごとのスキル・スロットを記録する非公式チェッカーです。"
            "名前やスキルで絞り込み、手元のアイテムを確認しながら登録できます。"
        ),
        steps=(
            "装飾品・固定護石は一覧から探して所持数を入力します。未所持のアイテムは0個として扱います。",
            "鑑定護石は個体ごとにレア度、スキル、スロットと個数を登録します。入力時の検証結果も確認してください。",
            "同じブラウザのスキルシミュレーターを開き、登録した所持情報を装備検索に利用します。",
        ),
        limitation=(
            "所持情報は利用中のブラウザに保存され、アカウントや端末間で自動同期されません。"
            "ブラウザのデータ削除に備えてJSONをダウンロードしてください。"
            "復元時は取込内容を確認し、統合または置換を選べます。"
            "このツールはゲームのセーブデータを読み取りません。"
        ),
        related_path=SIM_PATH,
        related_label="登録した所持情報でスキルシミュレーターを使う",
    ),
}

SITE_LINKS = (
    ("/game-guide/", "ゲーム攻略・ツール一覧"),
    ("/game-guide/mhwilds-guide/", "ワイルズツールの使い方"),
    ("/about/", "運営者情報"),
    ("/privacy/", "プライバシーポリシー"),
    ("/contact/", "お問い合わせ"),
)


class _Document(HTMLParser):
    """Locate head metadata without rewriting Vite's script or asset markup."""

    def __init__(self, source: str):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.line_offsets = [0]
        for line in source.splitlines(keepends=True):
            self.line_offsets.append(self.line_offsets[-1] + len(line))
        self.head = False
        self.head_end: list[int] = []
        self.body_start: list[int] = []
        self.body_end: list[int] = []
        self.title_start: int | None = None
        self.removals: list[tuple[int, int]] = []
        self.enriched = False

    def source_position(self) -> int:
        line, column = self.getpos()
        return self.line_offsets[line - 1] + column

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        offset = self.source_position()
        end = offset + len(self.get_starttag_text())
        if tag == "head":
            self.head = True
        elif tag == "body":
            self.body_start.append(end)
        if attributes.get("id") == "service-overview":
            self.enriched = True
        if not self.head:
            return
        if tag == "title":
            self.title_start = offset
        elif tag == "meta" and (
            (attributes.get("name") or "").lower() == "description"
            or (attributes.get("property") or "").lower().startswith("og:")
        ):
            self.removals.append((offset, end))
        elif (
            tag == "link"
            and "canonical" in (attributes.get("rel") or "").lower().split()
        ):
            self.removals.append((offset, end))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        offset = self.source_position()
        if tag == "title" and self.title_start is not None:
            self.removals.append((self.title_start, self.source.index(">", offset) + 1))
            self.title_start = None
        elif tag == "head":
            self.head_end.append(offset)
            self.head = False
        elif tag == "body":
            self.body_end.append(offset)


def enrich_html(source: str, app_path: str, stylesheet_url: str) -> str:
    """Add context only to a complete, previously unenriched application shell."""
    page = PAGES[app_path]
    if not stylesheet_url.startswith(f"/{app_path}/assets/") or any(
        character in stylesheet_url for character in '\\?#"<>\r\n'
    ):
        raise ValueError("Service stylesheet must use the application's assets path")
    document = _Document(source)
    document.feed(source)
    document.close()
    if (
        document.enriched
        or len(document.head_end) != 1
        or len(document.body_start) != 1
        or len(document.body_end) != 1
        or document.title_start is not None
    ):
        raise ValueError("Expected one complete, unenriched application HTML document")
    canonical = f"{ORIGIN}/{app_path}/"
    metadata = "\n".join(
        [
            f"<title>{escape(page.title)}</title>",
            f'<meta name="description" content="{escape(page.description)}">',
            f'<link rel="canonical" href="{canonical}">',
            '<meta property="og:type" content="website">',
            '<meta property="og:locale" content="ja_JP">',
            '<meta property="og:site_name" content="trinitrotorol">',
            f'<meta property="og:title" content="{escape(page.title)}">',
            f'<meta property="og:description" content="{escape(page.description)}">',
            f'<meta property="og:url" content="{canonical}">',
            f'<link rel="stylesheet" href="{escape(stylesheet_url)}">',
        ]
    )
    navigation = (
        '\n<nav class="service-context-nav" aria-label="サイトナビゲーション">'
        '<a href="/">trinitrotorol</a>'
        '<a href="/game-guide/">ゲーム攻略・ツール</a>'
        '<a href="/game-guide/mhwilds-guide/">使い方</a></nav>\n'
        '<noscript><main class="service-script-notice" '
        'aria-labelledby="service-no-script-title">'
        f'<h1 id="service-no-script-title">{escape(page.title.partition("｜")[0])}</h1>'
        "<p>"
        "検索や所持品の編集にはJavaScriptを有効にしてください。"
        "このページの説明と使い方の案内は、そのまま読むことができます。"
        '</p><p><a href="#service-overview">このツールの説明を読む</a></p>'
        '<p><a href="/game-guide/mhwilds-guide/">詳しい使い方を読む</a></p>'
        "</main></noscript>\n"
    )
    steps = "".join(f"<li>{escape(step)}</li>" for step in page.steps)
    links = "".join(
        f'<li><a href="{escape(url)}">{escape(label)}</a></li>'
        for url, label in SITE_LINKS
    )
    context = (
        '\n<section id="service-overview" class="service-page-details" '
        'aria-labelledby="service-overview-title">'
        f'<h2 id="service-overview-title">{escape(page.heading)}</h2>'
        f"<p>{escape(page.introduction)}</p>"
        f"<h3>使い方の流れ</h3><ol>{steps}</ol>"
        f"<h3>利用前に確認すること</h3><p>{escape(page.limitation)}</p>"
        '<p class="service-related-links">'
        '<a href="/game-guide/mhwilds-guide/">詳しい使い方と検索結果の見方</a>'
        f'<a href="/{escape(page.related_path)}/">{escape(page.related_label)}</a></p>'
        '<p class="service-independence">本サイトは個人が運営する非公式サイトです。'
        "ゲームの開発・販売元とは関係ありません。</p>"
        '<nav aria-label="サイト情報"><ul class="service-information-links">'
        f"{links}</ul></nav></section>\n"
    )
    edits = [(start, end, "") for start, end in document.removals]
    edits.extend(
        [
            (document.head_end[0], document.head_end[0], metadata + "\n"),
            (document.body_start[0], document.body_start[0], navigation),
            (document.body_end[0], document.body_end[0], context),
        ]
    )
    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    return source


def enrich_release_apps(output: Path) -> None:
    stylesheet = Path(__file__).with_name("service-html.css").read_bytes()
    stylesheet_name = f"service-info-{hashlib.sha256(stylesheet).hexdigest()[:16]}.css"
    for app_path in PAGES:
        app = output / app_path
        index = app / "index.html"
        enriched = enrich_html(
            index.read_text(encoding="utf-8"),
            app_path,
            f"/{app_path}/assets/{stylesheet_name}",
        )
        (app / "assets").mkdir(exist_ok=True)
        (app / "assets" / stylesheet_name).write_bytes(stylesheet)
        index.write_text(enriched, encoding="utf-8")
