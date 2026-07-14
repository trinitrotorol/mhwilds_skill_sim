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

import { fetchCatalogMetadata, searchRankedBuilds } from "./api";
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
  const selectedSkillIds = new Set(
    rows.map((row) => row.skillId).filter((skillId) => skillId !== ""),
  );
  const skillById = new Map(skills.map((skill) => [skill.skill_id, skill]));

  return (
    <fieldset className="form-section">
      <legend>{heading}</legend>
      <p className="section-description">{description}</p>

      {skills.length === 0 && (
        <p className="empty-note">選択できるスキルがありません。</p>
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
                <label htmlFor={skillInputId}>スキル</label>
                <select
                  aria-invalid={row.skillId === ""}
                  aria-label={`${heading} ${index + 1} のスキル`}
                  id={skillInputId}
                  onChange={(event) =>
                    onSkillChange(row.key, event.currentTarget.value)
                  }
                  value={row.skillId}
                >
                  <option value="">スキルを選択</option>
                  {skills.map((option) => (
                    <option
                      disabled={
                        option.skill_id !== row.skillId &&
                        selectedSkillIds.has(option.skill_id)
                      }
                      key={option.skill_id}
                      value={option.skill_id}
                    >
                      {displaySkillName(option)}（
                      {SKILL_KIND_LABELS[option.kind]}）
                    </option>
                  ))}
                </select>
              </div>

              <div className="field level-field">
                <label htmlFor={levelInputId}>{levelLabel}</label>
                <input
                  aria-describedby={!levelIsValid ? levelErrorId : undefined}
                  aria-invalid={!levelIsValid}
                  aria-label={`${heading} ${index + 1} の${levelLabel}`}
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
                    1から{maxLevel}の整数を入力してください。
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
  const decorationNames = new Map(
    metadata.decorations.map((decoration) => [
      decoration.decoration_id,
      decoration.display_name ?? decoration.decoration_id,
    ]),
  );
  const skillNames = new Map(
    metadata.skills.map((skill) => [
      skill.skill_id,
      skill.display_name ?? skill.skill_id,
    ]),
  );

  return (
    <section aria-labelledby="results-heading" className="results-section">
      <div aria-live="polite" className="search-status" role="status">
        {searchStatusMessage(response)}
      </div>

      <h2 id="results-heading">検索結果</h2>

      <div className="candidate-list">
        {response.candidates.map((candidate, candidateIndex) => (
          <article className="candidate-card" key={`candidate-${candidateIndex}`}>
            <div className="candidate-heading">
              <h3>候補 {candidateIndex + 1}</h3>
              <p>優先スコア: {candidate.preference_score}</p>
            </div>

            <section aria-labelledby={`equipment-${candidateIndex}`}>
              <h4 id={`equipment-${candidateIndex}`}>装備</h4>
              <ul className="equipment-list">
                {PARTS.map(([part, partLabel]) => {
                  const equipment = candidate.equipment.find(
                    (item) => item.part === part,
                  );
                  return (
                    <li className="equipment-row" key={part}>
                      <span className="part-label">{partLabel}</span>
                      <span className="result-value">
                        {equipment
                          ? equipment.display_name ?? equipment.equipment_id
                          : "該当装備なし"}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </section>

            <section aria-labelledby={`decorations-${candidateIndex}`}>
              <h4 id={`decorations-${candidateIndex}`}>装飾品</h4>
              {candidate.placements.length === 0 ? (
                <p className="empty-note">装飾品なし</p>
              ) : (
                <ul className="detail-list">
                  {candidate.placements.map((placement, placementIndex) => {
                    const equipment = candidate.equipment.find(
                      (item) => item.equipment_id === placement.equipment_id,
                    );
                    const equipmentName = equipment
                      ? equipment.display_name ?? equipment.equipment_id
                      : placement.equipment_id;
                    const decorationName =
                      decorationNames.get(placement.decoration_id) ??
                      placement.decoration_id;
                    return (
                      <li key={`placement-${placementIndex}`}>
                        <span className="result-value">{equipmentName}</span>
                        <span>スロット {placement.slot_index + 1}</span>
                        <strong className="result-value">{decorationName}</strong>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section aria-labelledby={`skills-${candidateIndex}`}>
              <h4 id={`skills-${candidateIndex}`}>発動スキル</h4>
              {candidate.skill_levels.length === 0 ? (
                <p className="empty-note">発動スキルなし</p>
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

export default function App() {
  const [metadataStatus, setMetadataStatus] =
    useState<MetadataStatus>("loading");
  const [metadata, setMetadata] = useState<CatalogMetadataResponse | null>(null);
  const [requiredRows, setRequiredRows] = useState<SkillRow[]>([]);
  const [preferenceRows, setPreferenceRows] = useState<SkillRow[]>([]);
  const [weaponKind, setWeaponKind] = useState("");
  const [maxResults, setMaxResults] = useState("5");
  const [isSearching, setIsSearching] = useState(false);
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
        const nameComparison = displaySkillName(left.skill).localeCompare(
          displaySkillName(right.skill),
          "ja",
        );
        if (nameComparison !== 0) {
          return nameComparison;
        }
        return left.index - right.index;
      })
      .map(({ skill }) => skill);
  }, [metadata]);

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

    try {
      const response = await searchRankedBuilds(payload, {
        signal: controller.signal,
      });
      if (!controller.signal.aborted) {
        setSearchResponse(response);
      }
    } catch (error: unknown) {
      if (!isAbortError(error) && !controller.signal.aborted) {
        setSearchError(
          "検索に失敗しました。時間をおいてもう一度お試しください。",
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
      <header className="site-header">
        <div className="header-content">
          <p className="eyebrow">装備構成検索</p>
          <h1>MHWILDS スキルシミュレータ</h1>
          <ul className="lead">
            <li>必須スキルはすべて満たす</li>
            <li>
              優先スキルは必須条件を満たしたうえで高いレベルを優先する
            </li>
          </ul>
          {metadata && metadataStatus === "ready" && (
            <p className="catalog-counts">
              スキル {metadata.counts.skills} / 装備 {metadata.counts.equipment} /
              装飾品 {metadata.counts.decorations}
            </p>
          )}
        </div>
      </header>

      <main className="main-content">
        {metadataStatus === "loading" && (
          <section aria-live="polite" className="state-card">
            <h2>データを読み込んでいます…</h2>
          </section>
        )}

        {metadataStatus === "unconfigured" && (
          <section className="state-card status-card" role="status">
            <p className="state-label">公開状況</p>
            <h2>検索APIを準備しています</h2>
            <p>
              Web画面は公開済みです。検索サーバーへ接続後、スキル検索をご利用いただけます。mock結果は表示しません。
            </p>
            <button
              className="primary-button compact-button"
              onClick={retryMetadata}
              type="button"
            >
              接続を再確認
            </button>
          </section>
        )}

        {metadataStatus === "error" && (
          <section aria-live="assertive" className="state-card error-card" role="alert">
            <p className="state-label">接続エラー</p>
            <h2>データを読み込めませんでした</h2>
            <p>時間をおいて接続を再確認してください。</p>
            <button
              className="primary-button compact-button"
              onClick={retryMetadata}
              type="button"
            >
              再試行
            </button>
          </section>
        )}

        {metadataStatus === "ready" && metadata && (
          <>
            <form className="search-form" onSubmit={handleSubmit}>
              <section aria-labelledby="search-conditions-heading" className="form-card">
                <div className="section-heading">
                  <p className="section-kicker">検索条件</p>
                  <h2 id="search-conditions-heading">装備構成を探す</h2>
                </div>

                <div className="top-fields">
                  <div className="field">
                    <label htmlFor="weapon-kind">武器種</label>
                    <select
                      id="weapon-kind"
                      onChange={(event) => setWeaponKind(event.currentTarget.value)}
                      value={weaponKind}
                    >
                      <option value="">指定なし</option>
                      {metadata.weapon_kinds.map((kind) => (
                        <option key={kind} value={kind}>
                          {kind}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="field">
                    <label htmlFor="max-results">表示件数</label>
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
                      <span className="field-error" id="max-results-error">
                        1から20の整数を入力してください。
                      </span>
                    )}
                  </div>
                </div>

                <SkillSection
                  addLabel="必須スキルを追加"
                  canAdd={canAddRequired}
                  description="すべて満たす必要があります"
                  heading="必須スキル"
                  levelLabel="最低レベル"
                  onAdd={() => addRow(setRequiredRows)}
                  onLevelChange={(key, level) =>
                    changeRowLevel(setRequiredRows, key, level)
                  }
                  onRemove={(key) => removeRow(setRequiredRows, key)}
                  onSkillChange={(key, skillId) =>
                    changeRowSkill(setRequiredRows, key, skillId)
                  }
                  removeLabel="必須スキルを削除"
                  rows={requiredRows}
                  sectionId="required"
                  skills={sortedSkills}
                />

                <SkillSection
                  addLabel="優先スキルを追加"
                  canAdd={canAddPreference}
                  description="必須条件を満たしたうえで、合計レベルが高い構成を優先します"
                  heading="優先スキル"
                  levelLabel="目標レベル"
                  onAdd={() => addRow(setPreferenceRows)}
                  onLevelChange={(key, level) =>
                    changeRowLevel(setPreferenceRows, key, level)
                  }
                  onRemove={(key) => removeRow(setPreferenceRows, key)}
                  onSkillChange={(key, skillId) =>
                    changeRowSkill(setPreferenceRows, key, skillId)
                  }
                  removeLabel="優先スキルを削除"
                  rows={preferenceRows}
                  sectionId="preference"
                  skills={sortedSkills}
                />

                <div className="submit-row">
                  <button
                    className="primary-button submit-button"
                    disabled={!formValid || isSearching}
                    type="submit"
                  >
                    {isSearching ? "検索中…" : "検索する"}
                  </button>
                </div>
              </section>
            </form>

            {searchError && (
              <div aria-live="assertive" className="search-error" role="alert">
                {searchError}
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
