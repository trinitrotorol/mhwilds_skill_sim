import { createContext, useContext } from "react";

export type Locale = "ja" | "en";
export const LOCALE_KEY = "mhwilds.ui.locale.v1";
export const LOCALE_EVENT = "mhwilds:locale-change";
export type NameKind = "skills" | "equipment" | "decorations";
export type EnglishNames = Record<NameKind, Record<string, string>>;
export const EMPTY_NAMES: EnglishNames = { skills: {}, equipment: {}, decorations: {} };

const ENGLISH: Record<string, string> = {
  "本文へ移動": "Skip to main content",
  "装備構成検索": "EQUIPMENT BUILD SEARCH",
  "MHWILDS スキルシミュレータ": "MHWILDS Skill Simulator",
  "サービス": "Tools",
  "所持品チェッカーへ": "Open inventory checker",
  "必須スキルはすべて満たす": "Every required skill must be satisfied",
  "優先スキルは必須条件を満たしたうえで高いレベルを優先する": "Among valid builds, prioritize higher levels of preferred skills",
  "スキル": "Skills", "装備": "Equipment", "装飾品": "Decorations",
  "武器": "Weapon", "防具": "Armor", "頭": "Head", "胴": "Chest", "腕": "Arms", "腰": "Waist", "脚": "Legs", "護石": "Charm", "シリーズ": "Series", "グループ": "Group",
  "データを読み込んでいます…": "Loading data…",
  "公開状況": "Service status", "検索APIを準備しています": "The search API is not available yet",
  "Web画面は公開済みです。検索サーバーへ接続後、スキル検索をご利用いただけます。mock結果は表示しません。": "The interface is available. Search will be available after connecting the search server. No simulated results are shown.",
  "接続を再確認": "Check connection again", "接続エラー": "Connection error", "データを読み込めませんでした": "Could not load data", "時間をおいて接続を再確認してください。": "Please wait a moment and try again.", "再試行": "Retry",
  "検索条件": "SEARCH CONDITIONS", "装備構成を探す": "Find an equipment build", "武器種": "Weapon type", "指定なし": "Any", "表示件数": "Maximum results",
  "選択できるスキルがありません。": "No skills are available.", "スキルを選択": "Select a skill",
  "必須スキルを追加": "Add required skill", "すべて満たす必要があります": "Every condition must be satisfied", "必須スキル": "Required skills", "最低レベル": "Minimum level", "必須スキルを削除": "Remove required skill",
  "優先スキルを追加": "Add preferred skill", "必須条件を満たしたうえで、合計レベルが高い構成を優先します": "Among builds satisfying all requirements, prioritize the highest total preferred skill levels", "優先スキル": "Preferred skills", "目標レベル": "Target level", "優先スキルを削除": "Remove preferred skill",
  "所持品と計算方法": "Inventory and search method", "所持品を考慮する": "Use owned inventory",
  "チェッカーと同じブラウザ内の保存データを使用します。未登録の装飾品は0個、護石は所持している個体のみを検索します。": "Use inventory saved by the checker in this browser and site. Unregistered decorations count as zero, and only owned charms are considered.",
  "カタログ変更を確認し、現在使えない所持品を検索から除外する（保存データは保持）": "Acknowledge catalog changes and exclude currently unusable items from this search (saved data is kept)",
  "計算方法": "Search method", "ブラウザ内で計算する": "Calculate in this browser", "利用可能ならサーバー、利用できなければブラウザ": "Use server if available; otherwise use browser",
  "サーバー検索が有効な場合のみ、検索に必要なスキル・所持数・護石能力を送信します。プロフィールID・名前・更新日時は送信しません。追加費用を防ぐため現在の公開設定はブラウザ計算です。": "Only when server search is enabled are the required skills, item quantities and charm abilities sent. Profile IDs, names and update times are never sent. This deployment uses browser calculation to avoid extra costs.",
  "検索中…": "Searching…", "検索する": "Search", "検索を中断": "Cancel search", "検索を中断しました。": "Search cancelled.", "ブラウザ内計算": "Browser calculation", "サーバー計算": "Server calculation",
  "検索に失敗しました。時間をおいてもう一度お試しください。": "Search failed. Please wait a moment and try again.",
  "時間内に探索が完了しませんでした。見つかった候補を表示します。": "The search reached its time limit. Showing the candidates found so far.", "時間内に候補を見つけられませんでした。": "No candidates were found before the time limit.", "条件を満たす装備構成が見つかりませんでした。": "No equipment builds satisfy these conditions.", "表示上限まで候補を表示しています。": "Showing the maximum number of candidates.",
  "検索結果": "Search results", "候補": "Candidate", "優先スコア:": "Preference score:", "該当装備なし": "No matching equipment", "装飾品なし": "No decorations", "スロット": "Slot", "発動スキル": "Active skills", "発動スキルなし": "No active skills",
  "所持品の状態": "Inventory status", "所持品を確認しています…": "Checking inventory…", "所持品は未登録です。チェッカーで登録してください。": "No inventory is registered. Add your items in the checker.", "所持品が未登録です。チェッカーで登録してください。": "No inventory is registered. Add your items in the checker.", "所持品とカタログの照合に失敗しました。検索条件を確認してください。": "Could not check inventory against the catalog. Review your search conditions.",
  "バックアップと現在のカタログのリビジョンが異なります。": "The backup and current catalog have different revisions.",
  "ブラウザ内の保存領域を利用できません。": "Browser storage is unavailable.", "ブラウザが保存領域へのアクセスを拒否しました。": "The browser denied access to storage.", "保存データが破損しているか未対応の形式です。元データを退避してから明示的に復旧してください。": "The saved data is damaged or uses an unsupported format. Back up the original data before explicitly restoring it.", "保存領域が不足しています。未保存の内容をJSONで退避してください。": "Storage is full. Export unsaved changes as JSON.", "保存に失敗しました。未保存の内容をJSONで退避してください。": "Could not save. Export unsaved changes as JSON.", "別の変更が保存されました。最新データを再読み込みしてください。": "Another change was saved. Reload the latest data.",
  "検索にはSHA-256で識別されたカタログが必要です。": "Search requires a catalog identified by SHA-256.", "検索用データが安全上の件数上限を超えています。所持上限を示すものではありません。": "The search data exceeds the processing safety limit. This is not an inventory limit.", "鑑定護石ルールが未取得です。": "Appraisal charm rules are unavailable.", "武器スロットは先頭に最大1個、防具スロットは最大3個です。": "At most one weapon slot may appear first, followed by at most three armor slots.", "スキルの種別またはレベルが不正です。": "Invalid skill type or level.", "レア度・スキル・スロットの組み合わせが取得済みルールに一致しません。": "The rarity, skills and slots do not match the available rules.",
  "検索結果の形式が不正です。": "The search result format is invalid.", "検索結果の装備が不正です。": "The search result contains invalid equipment.", "検索結果の装備がカタログと一致しません。": "The search result equipment does not match the catalog.", "検索結果が重複しています。": "The search contains duplicate results.", "検索結果の順位が不正です。": "The search result order is invalid.",
  "探索条件が広すぎるため、安全な処理上限に達しました。武器種・必須スキルを指定するか、所持品モードで候補を絞って再検索してください。候補なしという判定ではありません。": "The conditions are too broad and the processing safety limit was reached. Choose a weapon type or required skills, or use owned inventory to narrow the search. This does not mean that no valid builds exist.",
  "カタログURLが不正です。": "The catalog URL is invalid.", "カタログの形式がJSONではありません。": "The catalog is not JSON.", "カタログのサイズ上限を超えています。": "The catalog exceeds the size limit.", "カタログ読込を中断しました。": "Catalog loading was cancelled.", "カタログ形式が不正です。": "Invalid catalog format.", "カタログmanifestが不正です。": "Invalid catalog manifest.", "カタログの整合性検証に失敗しました。": "Catalog integrity verification failed.", "カタログのリビジョンが一致しません。再読み込みしてください。": "Catalog revisions do not match. Reload the page.", "公開設定が不正です。": "Invalid deployment configuration.", "公開機能設定が不正です。": "Invalid feature configuration.", "鑑定護石の公開設定とカタログが一致しません。": "The appraisal charm configuration does not match the catalog.",
  "great-sword": "Great Sword", "long-sword": "Long Sword", "sword-shield": "Sword & Shield", "dual-blades": "Dual Blades", "hammer": "Hammer", "hunting-horn": "Hunting Horn", "lance": "Lance", "gunlance": "Gunlance", "switch-axe": "Switch Axe", "charge-blade": "Charge Blade", "insect-glaive": "Insect Glaive", "light-bowgun": "Light Bowgun", "heavy-bowgun": "Heavy Bowgun", "bow": "Bow",
};

export function translate(locale: Locale, value: string): string {
  if (locale === "ja") return value;
  if (Object.hasOwn(ENGLISH, value)) return ENGLISH[value]!;
  const range = /^1から(\d+)の整数を入力してください。$/.exec(value);
  if (range) return `Enter a whole number from 1 to ${range[1]}.`;
  const count = /^(\d+)件の候補を表示しています。$/.exec(value);
  if (count) return `Showing ${count[1]} candidate${count[1] === "1" ? "" : "s"}.`;
  const field = /^(.*?) (\d+) の(.+)$/.exec(value);
  if (field) return `${translate(locale, field[1]!)} ${field[2]}: ${translate(locale, field[3]!)}`;
  // The node count is already formatted with the browser's locale. Preserve
  // its digits and separators, including decimal dots and nonbreaking spaces.
  const progress = /^(\d+)秒・(.+)件探索$/.exec(value);
  if (progress) return `${progress[1]}s · ${progress[2]} nodes explored`;
  const saved = /^所持品の保存日時: (.+)。検索開始時の保存内容を使います。$/.exec(value);
  if (saved) return `Inventory saved: ${saved[1]}. The saved snapshot at the start of the search is used.`;
  const prefixes: [string, string][] = [
    ["未解決の装飾品を保持: ", "Unresolved decoration retained: "],
    ["未解決の固定護石を保持: ", "Unresolved charm retained: "], ["現在のカタログにないスキル: ", "Skill missing from the current catalog: "], ["カタログ取得エラー ", "Catalog request failed "],
  ];
  if (value.startsWith("所持品の確認が必要です。")) {
    const warnings = value.slice("所持品の確認が必要です。".length)
      .split(/ (?=バックアップと|未解決の|鑑定護石 |検索には|検索用データが)/);
    return `Review your inventory. ${warnings.map((warning) => translate(locale, warning)).join(" ")}`;
  }
  // Identifier suffixes are opaque, including those containing Japanese text.
  for (const [from, to] of prefixes) if (value.startsWith(from)) return to + value.slice(from.length);
  const charm = /^鑑定護石 (.*?): (.*)$/.exec(value);
  if (charm) return `Appraisal charm ${charm[1]}: ${charm[2]!.split(/ (?=現在のカタログにないスキル: )/).map((issue) => translate(locale, issue)).join(" ")}`;
  return value;
}

export function readLocale(): Locale {
  try { return localStorage.getItem(LOCALE_KEY) === "en" ? "en" : "ja"; } catch { return "ja"; }
}

export function parseEnglishNames(value: unknown): EnglishNames {
  if (!value || typeof value !== "object") throw new Error("Invalid name dictionary");
  const doc = value as Record<string, unknown>;
  if (doc.schema_version !== 1 || doc.locale !== "en" || !doc.names || typeof doc.names !== "object") throw new Error("Invalid name dictionary");
  const result: EnglishNames = { skills: {}, equipment: {}, decorations: {} };
  for (const kind of ["skills", "equipment", "decorations"] as const) {
    const entries = (doc.names as Record<string, unknown>)[kind];
    if (!entries || typeof entries !== "object" || Array.isArray(entries)) throw new Error("Invalid name dictionary");
    for (const [id, name] of Object.entries(entries)) {
      if (typeof name !== "string" || !name.trim() || name.length > 500 || [...name].some((character) => character.charCodeAt(0) < 32)) throw new Error("Invalid name dictionary");
      Object.defineProperty(result[kind], id, { value: name, enumerable: true });
    }
  }
  return result;
}

export interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (text: string) => string;
  name: (kind: NameKind, id: string, fallback?: string | null) => string;
}
export const LocaleContext = createContext<LocaleContextValue>({
  locale: "ja", setLocale: () => {}, t: (text) => text,
  name: (_kind, id, fallback) => fallback ?? id,
});
export function useLocale(): LocaleContextValue { return useContext(LocaleContext); }
