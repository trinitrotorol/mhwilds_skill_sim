import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type FormEvent,
  type SetStateAction,
} from "react";

import { fetchCatalogMetadata, searchRankedBuilds, type Engine, type InventoryAcknowledgment } from "./service/search";
import { InventoryNotice } from "./service/InventoryNotice";
import { inventoryHref } from "./lib/paths";
import { LocaleProvider } from "./LocaleProvider";
import { useLocale } from "./i18n";
import type {
  CatalogMetadataResponse,
  RankedSearchRequestPayload,
  RankedSearchResponse,
} from "./types";

type MetadataStatus = "loading" | "ready" | "unconfigured" | "error";

interface SkillRow {
  key: number;
  skillId: string;
  level: string;
}

interface SkillSectionProps {
  addLabel: string;
  canAdd: boolean;
  description: string;
  heading: string;
  levelLabel: string;
  onAdd: () => void;
  onLevelChange: (key: number, level: string) => void;
  onRemove: (key: number) => void;
  onSkillChange: (key: number, skillId: string) => void;
  removeLabel: string;
  rows: SkillRow[];
  sectionId: string;
  skills: CatalogMetadataResponse["skills"];
}

const PARTS = [
  ["weapon", "武器"],
  ["head", "頭"],
  ["chest", "胴"],
  ["arms", "腕"],
  ["waist", "腰"],
  ["legs", "脚"],
  ["charm", "護石"],
] as const;

const SKILL_KIND_LABELS: Record<
  CatalogMetadataResponse["skills"][number]["kind"],
  string
> = {
  armor: "防具",
  weapon: "武器",
  set: "シリーズ",
  group: "グループ",
};

function isAbortError(error: unknown): boolean {
  return (
    error instanceof DOMException && error.name === "AbortError"
  ) || (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "AbortError"
  );
}

function isApiNotConfigured(error: unknown): boolean {
  if (typeof error !== "object" || error === null) {
    return false;
  }

  const value = error as { detail?: unknown; status?: unknown };
  return (
    value.status === 503 && value.detail === "search API is not configured"
  );
}

function displaySkillName(
  skill: CatalogMetadataResponse["skills"][number],
): string {
  return skill.display_name ?? skill.skill_id;
}

function clampLevel(level: string, maxLevel: number): string {
  const parsed = Number(level);
  const integerLevel = Number.isFinite(parsed) ? Math.trunc(parsed) : 1;
  return String(Math.min(maxLevel, Math.max(1, integerLevel)));
}

function isValidIntegerInRange(
  value: string,
  minimum: number,
  maximum: number,
): boolean {
  const parsed = Number(value);
  return (
    value.trim() !== "" &&
    Number.isInteger(parsed) &&
    parsed >= minimum &&
    parsed <= maximum
  );
}

function SkillSection({
  addLabel,
  canAdd,
  description,
  heading,
  levelLabel,
  onAdd,
  onLevelChange,
  onRemove,
  onSkillChange,
  removeLabel,
  rows,
  sectionId,
  skills,
}: SkillSectionProps) {
  const { locale, t, name } = useLocale();
  const selectedSkillIds = new Set(
    rows.map((row) => row.skillId).filter((skillId) => skillId !== ""),
  );
  const skillById = new Map(skills.map((skill) => [skill.skill_id, skill]));

  return (
    <fieldset className="form-section">
      <legend>{heading}</legend>
      <p className="section-description">{description}</p>

      {skills.length === 0 && (
        <p className="empty-note">{t("選択できるスキルがありません。")}</p>
      )}

      <div className="skill-rows">
        {rows.map((row, index) => {
          const skill = skillById.get(row.skillId);
          const maxLevel = skill?.max_level;
          const levelIsValid =
            maxLevel !== undefined &&
            isValidIntegerInRange(row.level, 1, maxLevel);
          const skillInputId = `${sectionId}-skill-${row.key}`;
          const levelInputId = `${sectionId}-level-${row.key}`;
          const levelErrorId = `${levelInputId}-error`;

          return (
            <div className="skill-row" key={row.key}>
              <div className="field skill-field">
                <label htmlFor={skillInputId}>{t("スキル")}</label>
                <select
                  aria-invalid={row.skillId === ""}
                  aria-label={t(`${heading} ${index + 1} のスキル`)}
                  id={skillInputId}
                  onChange={(event) =>
                    onSkillChange(row.key, event.currentTarget.value)
                  }
                  value={row.skillId}
                >
                  <option value="">{t("スキルを選択")}</option>
                  {skills.map((option) => (
                    <option
                      disabled={
                        option.skill_id !== row.skillId &&
                        selectedSkillIds.has(option.skill_id)
                      }
                      key={option.skill_id}
                      value={option.skill_id}
                    >
                      {name("skills", option.skill_id, option.display_name)}{locale === "ja" ? "（" : " ("}
                      {t(SKILL_KIND_LABELS[option.kind])}{locale === "ja" ? "）" : ")"}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field level-field">
                <label htmlFor={levelInputId}>{levelLabel}</label>
                <input
                  aria-describedby={!levelIsValid ? levelErrorId : undefined}
                  aria-invalid={!levelIsValid}
                  aria-label={t(`${heading} ${index + 1} の${levelLabel}`)}
                  disabled={!skill}
                  id={levelInputId}
                  inputMode="numeric"
                  max={maxLevel}
                  min="1"
                  onChange={(event) =>
                    onLevelChange(row.key, event.currentTarget.value)
                  }
                  step="1"
                  type="number"
                  value={row.level}
                />
                {!levelIsValid && skill && (
                  <span className="field-error" id={levelErrorId}>
                    {t(`1から${maxLevel}の整数を入力してください。`)}
                  </span>
                )}
              </div>

              <button
                className="secondary-button remove-button"
                onClick={() => onRemove(row.key)}
                type="button"
              >
                {removeLabel}
              </button>
            </div>
          );
        })}
      </div>

      <button
        className="secondary-button add-button"
        disabled={!canAdd}
        onClick={onAdd}
        type="button"
      >
        {addLabel}
      </button>
    </fieldset>
  );
}

function searchStatusMessage(response: RankedSearchResponse): string {
  if (response.timed_out) {
    return response.candidates.length > 0
      ? "時間内に探索が完了しませんでした。見つかった候補を表示します。"
      : "時間内に候補を見つけられませんでした。";
  }

  if (response.candidates.length === 0 && response.exhausted) {
    return "条件を満たす装備構成が見つかりませんでした。";
  }

  if (!response.exhausted) {
    return "表示上限まで候補を表示しています。";
  }

  return `${response.candidates.length}件の候補を表示しています。`;
}

interface CandidateListProps {
  metadata: CatalogMetadataResponse;
  response: RankedSearchResponse;
}

function CandidateList({ metadata, response }: CandidateListProps) {
  const { t, name } = useLocale();
  const decorationNames = new Map(
    metadata.decorations.map((decoration) => [
      decoration.decoration_id,
      name("decorations", decoration.decoration_id, decoration.display_name),
    ]),
  );
  const skillNames = new Map(
    metadata.skills.map((skill) => [
      skill.skill_id,
      name("skills", skill.skill_id, skill.display_name),
    ]),
  );

  return (
    <section aria-labelledby="results-heading" className="results-section">
      <div aria-live="polite" className="search-status" role="status">
        {t(searchStatusMessage(response))}
      </div>

      <h2 id="results-heading">{t("検索結果")}</h2>

      <div className="candidate-list">
        {response.candidates.map((candidate, candidateIndex) => (
          <article className="candidate-card" key={`candidate-${candidateIndex}`}>
            <div className="candidate-heading">
              <h3>{t("候補")} {candidateIndex + 1}</h3>
              <p>{t("優先スコア:")} {candidate.preference_score}</p>
            </div>

            <section aria-labelledby={`equipment-${candidateIndex}`}>
              <h4 id={`equipment-${candidateIndex}`}>{t("装備")}</h4>
              <ul className="equipment-list">
                {PARTS.map(([part, partLabel]) => {
                  const equipment = candidate.equipment.find(
                    (item) => item.part === part,
                  );
                  return (
                    <li className="equipment-row" key={part}>
                      <span className="part-label">{t(partLabel)}</span>
                      <span className="result-value">
                        {equipment
                          ? name("equipment", equipment.equipment_id, equipment.display_name)
                          : t("該当装備なし")}
                        {equipment && ([
                          ["シリーズ", equipment.series_skill_ids],
                          ["グループ", equipment.group_skill_ids],
                        ] as const).map(([label, ids]) => ids.length > 0 && (
                          <small className="equipment-bonus" key={label}>
                            {t(label)}: {ids.map((id) => skillNames.get(id) ?? id).join(", ")}
                          </small>
                        ))}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </section>

            <section aria-labelledby={`decorations-${candidateIndex}`}>
              <h4 id={`decorations-${candidateIndex}`}>{t("装飾品")}</h4>
              {candidate.placements.length === 0 ? (
                <p className="empty-note">{t("装飾品なし")}</p>
              ) : (
                <ul className="detail-list">
                  {candidate.placements.map((placement, placementIndex) => {
                    const equipment = candidate.equipment.find(
                      (item) => item.equipment_id === placement.equipment_id,
                    );
                    const equipmentName = equipment
                      ? name("equipment", equipment.equipment_id, equipment.display_name)
                      : placement.equipment_id;
                    const decorationName =
                      decorationNames.get(placement.decoration_id) ??
                      placement.decoration_id;
                    return (
                      <li key={`placement-${placementIndex}`}>
                        <span className="result-value">{equipmentName}</span>
                        <span>{t("スロット")} {placement.slot_index + 1}</span>
                        <strong className="result-value">{decorationName}</strong>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section aria-labelledby={`skills-${candidateIndex}`}>
              <h4 id={`skills-${candidateIndex}`}>{t("発動スキル")}</h4>
              {candidate.skill_levels.length === 0 ? (
                <p className="empty-note">{t("発動スキルなし")}</p>
              ) : (
                <ul className="skill-level-list">
                  {candidate.skill_levels.map((skillLevel, skillIndex) => (
                    <li key={`skill-level-${skillIndex}`}>
                      <span className="result-value">
                        {skillNames.get(skillLevel.skill_id) ??
                          skillLevel.skill_id}
                      </span>
                      <strong>Lv. {skillLevel.level}</strong>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </article>
        ))}
      </div>
    </section>
  );
}

function Simulator() {
  const { locale, setLocale, t, name } = useLocale();
  const [metadataStatus, setMetadataStatus] =
    useState<MetadataStatus>("loading");
  const [metadata, setMetadata] = useState<CatalogMetadataResponse | null>(null);
  const [requiredRows, setRequiredRows] = useState<SkillRow[]>([]);
  const [preferenceRows, setPreferenceRows] = useState<SkillRow[]>([]);
  const [weaponKind, setWeaponKind] = useState("");
  const [maxResults, setMaxResults] = useState("5");
  const [isSearching, setIsSearching] = useState(false);
  const [owned, setOwned] = useState(false);
  const [inventoryConfirmation, setInventoryConfirmation] = useState<InventoryAcknowledgment | null>(null);
  const [acknowledgeExclusions, setAcknowledgeExclusions] = useState<InventoryAcknowledgment | null>(null);
  const [engine, setEngine] = useState<Engine>("browser");
  const [activeEngine, setActiveEngine] = useState<string>("");
  const [progress, setProgress] = useState<string>("");
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResponse, setSearchResponse] =
    useState<RankedSearchResponse | null>(null);

  const metadataControllerRef = useRef<AbortController | null>(null);
  const metadataInFlightRef = useRef(false);
  const searchControllerRef = useRef<AbortController | null>(null);
  const searchInFlightRef = useRef(false);
  const nextRowKeyRef = useRef(1);

  const requestMetadata = useCallback(async () => {
    if (metadataInFlightRef.current) {
      return;
    }

    metadataInFlightRef.current = true;
    metadataControllerRef.current?.abort();
    const controller = new AbortController();
    metadataControllerRef.current = controller;

    try {
      const response = await fetchCatalogMetadata({ signal: controller.signal });
      if (controller.signal.aborted) {
        return;
      }
      setMetadata(response);
      setMetadataStatus("ready");
    } catch (error: unknown) {
      if (isAbortError(error) || controller.signal.aborted) {
        return;
      }
      setMetadataStatus(isApiNotConfigured(error) ? "unconfigured" : "error");
    } finally {
      if (metadataControllerRef.current === controller) {
        metadataControllerRef.current = null;
        metadataInFlightRef.current = false;
      }
    }
  }, []);

  useEffect(() => {
    const startRequest = window.setTimeout(() => {
      void requestMetadata();
    }, 0);

    return () => {
      window.clearTimeout(startRequest);
      metadataControllerRef.current?.abort();
      metadataControllerRef.current = null;
      metadataInFlightRef.current = false;
      searchControllerRef.current?.abort();
      searchControllerRef.current = null;
      searchInFlightRef.current = false;
    };
  }, [requestMetadata]);

  const retryMetadata = () => {
    if (metadataInFlightRef.current) {
      return;
    }
    setMetadataStatus("loading");
    setMetadata(null);
    void requestMetadata();
  };

  const sortedSkills = useMemo(() => {
    if (!metadata) {
      return [];
    }

    return metadata.skills
      .map((skill, index) => ({ index, skill }))
      .sort((left, right) => {
        const nameComparison = name("skills", left.skill.skill_id, displaySkillName(left.skill)).localeCompare(
          name("skills", right.skill.skill_id, displaySkillName(right.skill)),
          locale,
        );
        if (nameComparison !== 0) {
          return nameComparison;
        }
        return left.index - right.index;
      })
      .map(({ skill }) => skill);
  }, [metadata, locale, name]);

  const skillById = useMemo(
    () => new Map(sortedSkills.map((skill) => [skill.skill_id, skill])),
    [sortedSkills],
  );

  const addRow = (setter: Dispatch<SetStateAction<SkillRow[]>>) => {
    const key = nextRowKeyRef.current;
    nextRowKeyRef.current += 1;
    setter((rows) => [...rows, { key, skillId: "", level: "1" }]);
  };

  const removeRow = (
    setter: Dispatch<SetStateAction<SkillRow[]>>,
    key: number,
  ) => {
    setter((rows) => rows.filter((row) => row.key !== key));
  };

  const changeRowSkill = (
    setter: Dispatch<SetStateAction<SkillRow[]>>,
    key: number,
    skillId: string,
  ) => {
    setter((rows) => {
      if (
        skillId !== "" &&
        rows.some((row) => row.key !== key && row.skillId === skillId)
      ) {
        return rows;
      }

      const selectedSkill = skillById.get(skillId);
      return rows.map((row) =>
        row.key === key
          ? {
              ...row,
              skillId,
              level: selectedSkill
                ? clampLevel(row.level, selectedSkill.max_level)
                : row.level,
            }
          : row,
      );
    });
  };

  const changeRowLevel = (
    setter: Dispatch<SetStateAction<SkillRow[]>>,
    key: number,
    level: string,
  ) => {
    setter((rows) =>
      rows.map((row) => (row.key === key ? { ...row, level } : row)),
    );
  };

  const requiredRowsValid = requiredRows.every((row) => {
    const skill = skillById.get(row.skillId);
    return (
      skill !== undefined &&
      isValidIntegerInRange(row.level, 1, skill.max_level)
    );
  });
  const preferenceRowsValid = preferenceRows.every((row) => {
    const skill = skillById.get(row.skillId);
    return (
      skill !== undefined &&
      isValidIntegerInRange(row.level, 1, skill.max_level)
    );
  });
  const requiredIds = requiredRows.map((row) => row.skillId);
  const preferenceIds = preferenceRows.map((row) => row.skillId);
  const requiredUnique = new Set(requiredIds).size === requiredIds.length;
  const preferenceUnique =
    new Set(preferenceIds).size === preferenceIds.length;
  const maxResultsValid = isValidIntegerInRange(maxResults, 1, 20);
  const formValid =
    metadataStatus === "ready" &&
    metadata !== null &&
    requiredRowsValid &&
    preferenceRowsValid &&
    requiredUnique &&
    preferenceUnique &&
    maxResultsValid;

  const selectedRequiredCount = requiredRows.filter(
    (row) => row.skillId !== "",
  ).length;
  const selectedPreferenceCount = preferenceRows.filter(
    (row) => row.skillId !== "",
  ).length;
  const canAddRequired =
    sortedSkills.length > selectedRequiredCount &&
    requiredRows.every((row) => row.skillId !== "");
  const canAddPreference =
    sortedSkills.length > selectedPreferenceCount &&
    preferenceRows.every((row) => row.skillId !== "");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!metadata || !formValid || searchInFlightRef.current) {
      return;
    }

    const payload: RankedSearchRequestPayload = {
      requirements: requiredRows.map((row) => ({
        skill_id: row.skillId,
        min_level: Number(row.level),
      })),
      preferences: preferenceRows.map((row) => ({
        skill_id: row.skillId,
        target_level: Number(row.level),
      })),
      max_results: Number(maxResults),
      ...(weaponKind === "" ? {} : { weapon_kind: weaponKind }),
    };

    searchInFlightRef.current = true;
    searchControllerRef.current?.abort();
    const controller = new AbortController();
    searchControllerRef.current = controller;
    setIsSearching(true);
    setSearchError(null);
    setSearchResponse(null);
    setActiveEngine("");
    setProgress("");

    try {
      const response = await searchRankedBuilds(payload, {
        signal: controller.signal,
        owned,
        acknowledgeExclusions,
        engine,
        onEngine: (value) => { if (!controller.signal.aborted && searchControllerRef.current === controller) setActiveEngine(value === "browser" ? "ブラウザ内計算" : "サーバー計算"); },
        onProgress: (value) => { if (!controller.signal.aborted && searchControllerRef.current === controller) setProgress(`${Math.round(value.elapsed_ms / 1000)}秒・${value.visited_nodes.toLocaleString()}件探索`); },
      });
      if (!controller.signal.aborted) {
        setSearchResponse(response);
      }
    } catch (error: unknown) {
      if (!isAbortError(error) && !controller.signal.aborted) {
        setSearchError(
          error instanceof Error ? error.message : "検索に失敗しました。時間をおいてもう一度お試しください。",
        );
      }
    } finally {
      if (searchControllerRef.current === controller) {
        searchControllerRef.current = null;
        searchInFlightRef.current = false;
        setIsSearching(false);
      }
    }
  };

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">{t("本文へ移動")}</a>
      <header className="site-header">
        <div className="header-content">
          <p className="eyebrow">{t("装備構成検索")}</p>
          <h1>{t("MHWILDS スキルシミュレータ")}</h1>
          <div className="field language-control">
            <label htmlFor="ui-locale">言語 / Language</label>
            <select id="ui-locale" value={locale} onChange={(event) => setLocale(event.currentTarget.value === "en" ? "en" : "ja")}>
              <option value="ja" lang="ja">日本語</option>
              <option value="en" lang="en">English</option>
            </select>
          </div>
          <nav aria-label={t("サービス")}><a href={inventoryHref(import.meta.env.BASE_URL, window.location.search)}>{t("所持品チェッカーへ")}</a></nav>
          <ul className="lead">
            <li>{t("必須スキルはすべて満たす")}</li>
            <li>{t("優先スキルは必須条件を満たしたうえで高いレベルを優先する")}</li>
          </ul>
          {metadata && metadataStatus === "ready" && (
            <p className="catalog-counts">
              {t("スキル")} {metadata.counts.skills} / {t("装備")} {metadata.counts.equipment} /{" "}
              {t("装飾品")} {metadata.counts.decorations}
            </p>
          )}
        </div>
      </header>

      <main className="main-content" id="main-content">
        {metadataStatus === "loading" && (
          <section aria-live="polite" className="state-card">
            <h2>{t("データを読み込んでいます…")}</h2>
          </section>
        )}

        {metadataStatus === "unconfigured" && (
          <section className="state-card status-card" role="status">
            <p className="state-label">{t("公開状況")}</p>
            <h2>{t("検索APIを準備しています")}</h2>
            <p>{t("Web画面は公開済みです。検索サーバーへ接続後、スキル検索をご利用いただけます。mock結果は表示しません。")}</p>
            <button
              className="primary-button compact-button"
              onClick={retryMetadata}
              type="button"
            >{t("接続を再確認")}</button>
          </section>
        )}

        {metadataStatus === "error" && (
          <section aria-live="assertive" className="state-card error-card" role="alert">
            <p className="state-label">{t("接続エラー")}</p>
            <h2>{t("データを読み込めませんでした")}</h2>
            <p>{t("時間をおいて接続を再確認してください。")}</p>
            <button
              className="primary-button compact-button"
              onClick={retryMetadata}
              type="button"
            >{t("再試行")}</button>
          </section>
        )}

        {metadataStatus === "ready" && metadata && (
          <>
            <form className="search-form" onSubmit={handleSubmit}>
              <section aria-labelledby="search-conditions-heading" className="form-card">
                <div className="section-heading">
                  <p className="section-kicker">{t("検索条件")}</p>
                  <h2 id="search-conditions-heading">{t("装備構成を探す")}</h2>
                </div>

                <div className="top-fields">
                  <div className="field">
                    <label htmlFor="weapon-kind">{t("武器種")}</label>
                    <select
                      id="weapon-kind"
                      onChange={(event) => setWeaponKind(event.currentTarget.value)}
                      value={weaponKind}
                    >
                      <option value="">{t("指定なし")}</option>
                      {metadata.weapon_kinds.map((kind) => (
                        <option key={kind} value={kind}>
                          {t(kind)}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="field">
                    <label htmlFor="max-results">{t("表示件数")}</label>
                    <input
                      aria-describedby={!maxResultsValid ? "max-results-error" : undefined}
                      aria-invalid={!maxResultsValid}
                      id="max-results"
                      inputMode="numeric"
                      max="20"
                      min="1"
                      onChange={(event) => setMaxResults(event.currentTarget.value)}
                      step="1"
                      type="number"
                      value={maxResults}
                    />
                    {!maxResultsValid && (
                      <span className="field-error" id="max-results-error">{t("1から20の整数を入力してください。")}</span>
                    )}
                  </div>
                </div>

                <SkillSection
                  addLabel={t("必須スキルを追加")}
                  canAdd={canAddRequired}
                  description={t("すべて満たす必要があります")}
                  heading={t("必須スキル")}
                  levelLabel={t("最低レベル")}
                  onAdd={() => addRow(setRequiredRows)}
                  onLevelChange={(key, level) =>
                    changeRowLevel(setRequiredRows, key, level)
                  }
                  onRemove={(key) => removeRow(setRequiredRows, key)}
                  onSkillChange={(key, skillId) =>
                    changeRowSkill(setRequiredRows, key, skillId)
                  }
                  removeLabel={t("必須スキルを削除")}
                  rows={requiredRows}
                  sectionId="required"
                  skills={sortedSkills}
                />

                <SkillSection
                  addLabel={t("優先スキルを追加")}
                  canAdd={canAddPreference}
                  description={t("必須条件を満たしたうえで、合計レベルが高い構成を優先します")}
                  heading={t("優先スキル")}
                  levelLabel={t("目標レベル")}
                  onAdd={() => addRow(setPreferenceRows)}
                  onLevelChange={(key, level) =>
                    changeRowLevel(setPreferenceRows, key, level)
                  }
                  onRemove={(key) => removeRow(setPreferenceRows, key)}
                  onSkillChange={(key, skillId) =>
                    changeRowSkill(setPreferenceRows, key, skillId)
                  }
                  removeLabel={t("優先スキルを削除")}
                  rows={preferenceRows}
                  sectionId="preference"
                  skills={sortedSkills}
                />

                <div className="submit-row">
                  <fieldset className="form-section">
                    <legend>{t("所持品と計算方法")}</legend>
                    <label><input type="checkbox" checked={owned} onChange={(event) => { setOwned(event.currentTarget.checked); setAcknowledgeExclusions(null); }} />{t("所持品を考慮する")}</label>
                    <p>{t("チェッカーと同じブラウザ内の保存データを使用します。未登録の装飾品は0個、護石は所持している個体のみを検索します。")}</p>
                    {owned && <InventoryNotice onStateChange={setInventoryConfirmation} />}
                    {owned && <label><input type="checkbox" disabled={!inventoryConfirmation} checked={Boolean(inventoryConfirmation && acknowledgeExclusions?.raw === inventoryConfirmation.raw && acknowledgeExclusions?.catalogRevision === inventoryConfirmation.catalogRevision)} onChange={(event) => setAcknowledgeExclusions(event.currentTarget.checked ? inventoryConfirmation : null)} />{t("カタログ変更を確認し、現在使えない所持品を検索から除外する（保存データは保持）")}</label>}
                    <label htmlFor="search-engine">{t("計算方法")}</label>
                    <select id="search-engine" value={engine} onChange={(event) => setEngine(event.currentTarget.value as Engine)}>
                      <option value="browser">{t("ブラウザ内で計算する")}</option>
                      <option value="auto">{t("利用可能ならサーバー、利用できなければブラウザ")}</option>
                    </select>
                    <p>{t("サーバー検索が有効な場合のみ、検索に必要なスキル・所持数・護石能力を送信します。プロフィールID・名前・更新日時は送信しません。追加費用を防ぐため現在の公開設定はブラウザ計算です。")}</p>
                  </fieldset>
                  <button
                    className="primary-button submit-button"
                    disabled={!formValid || isSearching}
                    type="submit"
                  >
                    {t(isSearching ? "検索中…" : "検索する")}
                  </button>
                  {isSearching && <button type="button" onClick={() => { searchControllerRef.current?.abort(); searchControllerRef.current = null; searchInFlightRef.current = false; setIsSearching(false); setProgress("検索を中断しました。"); }}>{t("検索を中断")}</button>}
                </div>
                <p role="status">{t(activeEngine)}{progress && `${locale === "ja" ? "・" : " · "}${t(progress)}`}</p>
              </section>
            </form>

            {searchError && (
              <div aria-live="assertive" className="search-error" role="alert">
                {t(searchError)}
              </div>
            )}

            {searchResponse && (
              <CandidateList metadata={metadata} response={searchResponse} />
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default function App() {
  return <LocaleProvider><Simulator /></LocaleProvider>;
}
