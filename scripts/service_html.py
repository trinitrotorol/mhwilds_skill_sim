"""Visible, crawlable context for the two static applications in a release."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path

ROOT_ORIGIN = "https://trinitrotorol.com"
ORIGIN = "https://mhwilds.trinitrotorol.com"
SIM_PATH = "skill-sim"
CHECKER_PATH = "inventory"
LEGACY_SIM_PATH = "game-guide/mhwilds-skill-sim"
LEGACY_CHECKER_PATH = "game-guide/mhwilds-inventory-checker"
LEGACY_PATHS = {LEGACY_SIM_PATH: SIM_PATH, LEGACY_CHECKER_PATH: CHECKER_PATH}


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

ENGLISH_PAGES = {
    SIM_PATH: ServicePage(
        title="Monster Hunter Wilds Skill Simulator | Equipment & Skills | trinitrotorol",
        description=(
            "Find Monster Hunter Wilds equipment builds for your skill requirements. "
            "Include owned decorations, standard charms and appraised charms in this "
            "unofficial browser-based skill simulator."
        ),
        heading="Find equipment builds that fit your skills and inventory",
        introduction=(
            "Choose the skills and levels you want in Monster Hunter Wilds to find "
            "combinations of weapons, armor, charms and decorations. "
            "This unofficial simulator helps you compare equipment options."
        ),
        steps=(
            "Choose weapon and armor skills, series skills or group skills, then set your requirements.",
            "To use your own items, register decorations and charms in the inventory checker and enable inventory-aware search.",
            "Check the equipment, active skills and decoration placements in each result. If no build is found, try fewer requirements.",
        ),
        limitation=(
            "Search runs in your browser. Its duration depends on your device and requirements. "
            "Reaching a time or other limit may return partial results from the search completed so far. "
            "Manually cancelling a search does not show results. Check whether the search finished, "
            "was cancelled or found no builds. Game updates may cause differences between "
            "the catalog and the game."
        ),
        related_path=CHECKER_PATH,
        related_label="Register decorations and charms in the inventory checker",
    ),
    CHECKER_PATH: ServicePage(
        title="Monster Hunter Wilds Inventory Checker | Decorations & Charms | trinitrotorol",
        description=(
            "Track owned decorations, standard charms and appraised charms in Monster Hunter Wilds. "
            "Save locally in your browser, back up to JSON, and use your inventory in the skill simulator."
        ),
        heading="Organize decorations and charms for equipment searches",
        introduction=(
            "This unofficial Monster Hunter Wilds checker records decoration and standard charm "
            "quantities, plus each appraised charm's skills and slots. "
            "Filter by name or skill while registering your items."
        ),
        steps=(
            "Find decorations and standard charms in the list and enter their quantities. Items with a quantity of zero are treated as unowned.",
            "Register each appraised charm's skills, levels, slots, rarity and quantity, and check any validation messages.",
            "Open the skill simulator in the same browser to include your registered inventory in equipment searches.",
        ),
        limitation=(
            "Inventory is saved in this browser and does not automatically sync across accounts or devices. "
            "Download a JSON backup before clearing browser data. Review imported data before choosing "
            "to merge or replace your inventory. This tool does not read game save files."
        ),
        related_path=SIM_PATH,
        related_label="Use your inventory in the skill simulator",
    ),
}

SITE_LINKS = (
    (f"{ROOT_ORIGIN}/game-guide/", "ゲーム攻略・ツール一覧"),
    (f"{ROOT_ORIGIN}/game-guide/mhwilds-guide/", "ワイルズツールの使い方"),
    (f"{ROOT_ORIGIN}/about/", "運営者情報"),
    (f"{ROOT_ORIGIN}/privacy/", "プライバシーポリシー"),
    (f"{ROOT_ORIGIN}/contact/", "お問い合わせ"),
)

ENGLISH_SITE_LABELS = (
    "Game guides and tools (Japanese)",
    "Wilds tool guide (Japanese)",
    "About this site (Japanese)",
    "Privacy policy (Japanese)",
    "Contact (Japanese)",
)


def bilingual(japanese: str, english: str) -> str:
    """Keep one semantic element; CSS hides the inactive language from all users."""
    return (
        f'<span data-service-lang="ja" lang="ja">{escape(japanese)}</span>'
        f'<span data-service-lang="en" lang="en">{escape(english)}</span>'
    )


def translated_attribute(attribute: str, japanese: str, english: str) -> str:
    return (
        f'{attribute}="{escape(japanese)}" '
        f'data-service-{attribute}-ja="{escape(japanese)}" '
        f'data-service-{attribute}-en="{escape(english)}"'
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


def enrich_html(
    source: str,
    app_path: str,
    stylesheet_url: str,
    locale_script_url: str | None = None,
) -> str:
    """Add context only to a complete, previously unenriched application shell."""
    canonical_path = LEGACY_PATHS.get(app_path, app_path)
    legacy = app_path in LEGACY_PATHS
    page = PAGES[canonical_path]
    english = ENGLISH_PAGES[canonical_path]
    if not stylesheet_url.startswith(f"/{app_path}/assets/") or any(
        character in stylesheet_url for character in '\\?#"<>\r\n'
    ):
        raise ValueError("Service stylesheet must use the application's assets path")
    if locale_script_url is not None and (
        not locale_script_url.startswith(f"/{app_path}/assets/")
        or any(character in locale_script_url for character in '\\?#"<>\r\n')
    ):
        raise ValueError("Service locale script must use the application's assets path")
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
    canonical = f"{ORIGIN}/{canonical_path}/"
    metadata = "\n".join(
        [
            "<title "
            f'data-service-text-ja="{escape(page.title)}" '
            f'data-service-text-en="{escape(english.title)}">{escape(page.title)}</title>',
            '<meta name="description" '
            f"{translated_attribute('content', page.description, english.description)}>",
            f'<link rel="canonical" href="{canonical}">',
            '<meta property="og:type" content="website">',
            '<meta property="og:locale" '
            f"{translated_attribute('content', 'ja_JP', 'en_US')}>",
            '<meta property="og:site_name" content="trinitrotorol">',
            '<meta property="og:title" '
            f"{translated_attribute('content', page.title, english.title)}>",
            '<meta property="og:description" '
            f"{translated_attribute('content', page.description, english.description)}>",
            f'<meta property="og:url" content="{canonical}">',
            f'<link rel="stylesheet" href="{escape(stylesheet_url)}">',
        ]
    )
    if locale_script_url is not None:
        metadata += (
            f'\n<script type="module" src="{escape(locale_script_url)}"></script>'
        )
    if legacy:
        metadata += '\n<meta name="robots" content="noindex,follow">'
    migration = ""
    if legacy:
        old_checker = f"{ROOT_ORIGIN}/{LEGACY_CHECKER_PATH}/?legacy=1"
        migration = (
            '<aside class="service-migration-notice" aria-labelledby="service-migration-title">'
            '<h2 id="service-migration-title">'
            + bilingual(
                "移転前の所持情報を取り出すページです",
                "Recover inventory saved on the old site",
            )
            + "</h2><p>"
            + bilingual(
                "ワイルズのツールは専用サイトへ移転しました。この旧サイトの保存データは残っています。新サイトへは自動で引き継がれません。",
                "The Wilds tools have moved to a dedicated site. Inventory saved on this old site is still available, but is not transferred automatically.",
            )
            + '</p><ol><li><a href="'
            + old_checker
            + '">'
            + bilingual("旧所持品チェッカー", "Old inventory checker")
            + "</a>"
            + bilingual(
                "で「JSONをダウンロード」を選びます。",
                ': choose "Download JSON" to save a backup.',
            )
            + '</li><li><a href="'
            + f"{ORIGIN}/{CHECKER_PATH}/"
            + '">'
            + bilingual("新しい所持品チェッカー", "New inventory checker")
            + "</a>"
            + bilingual(
                "で「JSONから復元」を選びます。取込内容を確認して統合または置換を選べます。",
                ': choose "Restore from JSON", review the imported data, then merge or replace your inventory.',
            )
            + f'</li></ol><p><a href="{canonical}">'
            + bilingual(
                "新しいサイトでこのツールを開く", "Open this tool on the new site"
            )
            + "</a></p></aside>\n"
        )
        related_legacy = next(
            path
            for path, current in LEGACY_PATHS.items()
            if current == page.related_path
        )
        related_url = f"/{related_legacy}/?legacy=1"
    else:
        related_url = f"/{page.related_path}/"
    navigation = (
        '\n<nav class="service-context-nav" '
        f"{translated_attribute('aria-label', 'サイトナビゲーション', 'Site navigation')}>"
        f'<a href="{ROOT_ORIGIN}/">trinitrotorol</a>'
        f'<a href="{ROOT_ORIGIN}/game-guide/">'
        f"{bilingual('ゲーム攻略・ツール', 'Game guides and tools (Japanese)')}</a>"
        f'<a href="{ROOT_ORIGIN}/game-guide/mhwilds-guide/">'
        f"{bilingual('使い方', 'User guide (Japanese)')}</a></nav>\n"
        f"{migration}"
        '<noscript><main class="service-script-notice" '
        'aria-labelledby="service-no-script-title">'
        '<h1 id="service-no-script-title">'
        f"{bilingual(page.title.partition('｜')[0], english.title.partition(' | ')[0])}</h1>"
        "<p>"
        + bilingual(
            "検索や所持品の編集にはJavaScriptを有効にしてください。このページの説明と使い方の案内は、そのまま読むことができます。",
            "Enable JavaScript to search or edit inventory. You can still read this page's overview and instructions.",
        )
        + '</p><p><a href="#service-overview">'
        + bilingual("このツールの説明を読む", "Read the tool overview")
        + f'</a></p><p><a href="{ROOT_ORIGIN}/game-guide/mhwilds-guide/">'
        + bilingual("詳しい使い方を読む", "Read the full guide (Japanese)")
        + "</a></p>"
        "</main></noscript>\n"
    )
    steps = "".join(
        f"<li>{bilingual(step, english_step)}</li>"
        for step, english_step in zip(page.steps, english.steps)
    )
    links = "".join(
        f'<li><a href="{escape(url)}">{bilingual(label, english_label)}</a></li>'
        for (url, label), english_label in zip(SITE_LINKS, ENGLISH_SITE_LABELS)
    )
    context = (
        '\n<section id="service-overview" class="service-page-details" '
        'aria-labelledby="service-overview-title">'
        f'<h2 id="service-overview-title">{bilingual(page.heading, english.heading)}</h2>'
        f"<p>{bilingual(page.introduction, english.introduction)}</p>"
        f"<h3>{bilingual('使い方の流れ', 'How to use this tool')}</h3><ol>{steps}</ol>"
        f"<h3>{bilingual('利用前に確認すること', 'Before you start')}</h3>"
        f"<p>{bilingual(page.limitation, english.limitation)}</p>"
        '<p class="service-related-links">'
        f'<a href="{ROOT_ORIGIN}/game-guide/mhwilds-guide/">'
        f"{bilingual('詳しい使い方と検索結果の見方', 'Usage and search result guide (Japanese)')}</a>"
        f'<a href="{escape(related_url)}">{bilingual(page.related_label, english.related_label)}</a></p>'
        '<p class="service-independence">'
        + bilingual(
            "本サイトは個人が運営する非公式サイトです。ゲームの開発・販売元とは関係ありません。",
            "This unofficial site is independently operated and is not affiliated with the game's developer or publisher.",
        )
        + "</p><nav "
        + translated_attribute("aria-label", "サイト情報", "Site information")
        + '><ul class="service-information-links">'
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
    locale_script = Path(__file__).with_name("service-locale.mjs").read_bytes()
    locale_script_name = (
        f"service-locale-{hashlib.sha256(locale_script).hexdigest()[:16]}.js"
    )
    for app_path in [*PAGES, *LEGACY_PATHS]:
        app = output / app_path
        index = app / "index.html"
        enriched = enrich_html(
            index.read_text(encoding="utf-8"),
            app_path,
            f"/{app_path}/assets/{stylesheet_name}",
            f"/{app_path}/assets/{locale_script_name}",
        )
        (app / "assets").mkdir(exist_ok=True)
        (app / "assets" / stylesheet_name).write_bytes(stylesheet)
        (app / "assets" / locale_script_name).write_bytes(locale_script)
        index.write_text(enriched, encoding="utf-8")
