import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchCatalogMetadata, searchRankedBuilds } from "./api";
import App from "./App";
import type {
  CatalogMetadataResponse,
  EquipmentResponse,
  RankedBuildCandidate,
  RankedSearchResponse,
} from "./types";

vi.mock("./api", () => ({
  fetchCatalogMetadata: vi.fn(),
  searchRankedBuilds: vi.fn(),
}));

const fetchCatalogMetadataMock = vi.mocked(fetchCatalogMetadata);
const searchRankedBuildsMock = vi.mocked(searchRankedBuilds);

const METADATA: CatalogMetadataResponse = {
  schema_version: 1,
  skills: [
    {
      skill_id: "skill_attack",
      display_name: "攻撃",
      kind: "weapon",
      max_level: 7,
      ranks: [],
    },
    {
      skill_id: "skill_critical_eye",
      display_name: "見切り",
      kind: "armor",
      max_level: 5,
      ranks: [],
    },
    {
      skill_id: "fallback_skill",
      display_name: null,
      kind: "group",
      max_level: 3,
      ranks: [],
    },
  ],
  weapon_kinds: ["great-sword", "long-sword"],
  decorations: [
    {
      decoration_id: "deco_known",
      display_name: "達人珠",
      required_slot: { kind: "armor", level: 1 },
      skills: [{ skill_id: "skill_critical_eye", level: 1 }],
    },
  ],
  features: {
    artian_series_skill_assignment: true,
    artian_group_skill_assignment: true,
    theoretical_appraisal_charms: false,
  },
  counts: {
    skills: 3,
    equipment: 2085,
    decorations: 1,
    appraisal_charm_skill_groups: 0,
    appraisal_charm_patterns: 0,
  },
};

const PARTS: EquipmentResponse["part"][] = [
  "weapon",
  "head",
  "chest",
  "arms",
  "waist",
  "legs",
  "charm",
];

function equipment(
  part: EquipmentResponse["part"],
  equipmentId: string,
  displayName: string | null,
): EquipmentResponse {
  return {
    equipment_id: equipmentId,
    display_name: displayName,
    part,
    weapon_kind: part === "weapon" ? "long-sword" : null,
    series_skill_id: null,
    group_skill_id: null,
    series_skill_ids: [],
    group_skill_ids: [],
    skills: [],
    slots: [],
  };
}

const FIRST_CANDIDATE: RankedBuildCandidate = {
  equipment: [
    equipment("weapon", "duplicate-equipment-id", "鉄の武器"),
    equipment("head", "duplicate-equipment-id", null),
    equipment("chest", "chest-id", "狩人の胴"),
    equipment("arms", "arms-id", "狩人の腕"),
    equipment("waist", "waist-id", "狩人の腰"),
    equipment("legs", "legs-id", "狩人の脚"),
    equipment("charm", "charm-id", "攻撃の護石"),
  ],
  placements: [
    {
      equipment_id: "chest-id",
      slot_index: 0,
      decoration_id: "deco_known",
    },
    {
      equipment_id: "arms-id",
      slot_index: 2,
      decoration_id: "unknown_deco",
    },
  ],
  skill_levels: [
    { skill_id: "skill_critical_eye", level: 5 },
    { skill_id: "unknown_skill", level: 2 },
  ],
  preference_score: 2,
};

const SECOND_CANDIDATE: RankedBuildCandidate = {
  equipment: PARTS.map((part) => equipment(part, `second-${part}`, `第二 ${part}`)),
  placements: [],
  skill_levels: [],
  preference_score: 99,
};

const EMPTY_EXHAUSTED: RankedSearchResponse = {
  candidates: [],
  exhausted: true,
  timed_out: false,
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

async function renderReady() {
  const user = userEvent.setup();
  render(<App />);
  await screen.findByRole("heading", { name: "装備構成を探す" });
  return user;
}

beforeEach(() => {
  fetchCatalogMetadataMock.mockReset();
  searchRankedBuildsMock.mockReset();
  fetchCatalogMetadataMock.mockResolvedValue(METADATA);
  searchRankedBuildsMock.mockResolvedValue(EMPTY_EXHAUSTED);
});

describe("metadata", () => {
  it("shows loading, then API counts, skill options, and weapon kinds in API order", async () => {
    const metadataRequest = deferred<CatalogMetadataResponse>();
    fetchCatalogMetadataMock.mockImplementationOnce(() => metadataRequest.promise);

    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByText("データを読み込んでいます…")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "検索する" })).not.toBeInTheDocument();

    await act(async () => metadataRequest.resolve(METADATA));

    expect(
      await screen.findByText("スキル 3 / 装備 2085 / 装飾品 1"),
    ).toBeInTheDocument();

    const weaponOptions = within(screen.getByLabelText("武器種"))
      .getAllByRole("option")
      .map((option) => option.textContent);
    expect(weaponOptions).toEqual(["指定なし", "great-sword", "long-sword"]);

    await user.click(screen.getByRole("button", { name: "必須スキルを追加" }));
    const skillSelect = screen.getByLabelText("必須スキル 1 のスキル");
    expect(
      within(skillSelect).getByRole("option", { name: "攻撃（武器）" }),
    ).toHaveValue("skill_attack");
    expect(
      within(skillSelect).getByRole("option", { name: "見切り（防具）" }),
    ).toHaveValue("skill_critical_eye");
    expect(
      within(skillSelect).getByRole("option", {
        name: "fallback_skill（グループ）",
      }),
    ).toHaveValue("fallback_skill");
  });

  it("renders the intentional API-unconfigured state and retries", async () => {
    fetchCatalogMetadataMock
      .mockRejectedValueOnce(
        Object.assign(new Error("unconfigured"), {
          status: 503,
          detail: "search API is not configured",
        }),
      )
      .mockResolvedValueOnce(METADATA);

    const user = userEvent.setup();
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "検索APIを準備しています" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "検索APIを準備しています",
    );
    expect(screen.getByText(/Web画面は公開済みです/)).toHaveTextContent(
      "mock結果は表示しません",
    );
    expect(screen.queryByText("現在準備中です。")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "検索する" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "接続を再確認" }));
    expect(
      await screen.findByRole("heading", { name: "装備構成を探す" }),
    ).toBeInTheDocument();
    expect(fetchCatalogMetadataMock).toHaveBeenCalledTimes(2);
  });

  it("renders a live general error and retries", async () => {
    fetchCatalogMetadataMock
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce(METADATA);

    const user = userEvent.setup();
    render(<App />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("データを読み込めませんでした");
    expect(screen.queryByRole("button", { name: "検索する" })).not.toBeInTheDocument();

    await user.click(within(alert).getByRole("button", { name: "再試行" }));
    expect(
      await screen.findByRole("heading", { name: "装備構成を探す" }),
    ).toBeInTheDocument();
  });

  it("aborts metadata loading on unmount", async () => {
    let requestSignal: AbortSignal | undefined;
    fetchCatalogMetadataMock.mockImplementationOnce((options) => {
      requestSignal = options?.signal;
      return new Promise<CatalogMetadataResponse>(() => undefined);
    });

    const { unmount } = render(<App />);
    await waitFor(() => expect(requestSignal).toBeDefined());
    expect(requestSignal?.aborted).toBe(false);
    unmount();
    expect(requestSignal?.aborted).toBe(true);
  });

  it("handles an empty skill catalog without inventing options", async () => {
    const emptyMetadata: CatalogMetadataResponse = {
      ...METADATA,
      skills: [],
      decorations: [],
      counts: { ...METADATA.counts, skills: 0, decorations: 0 },
    };
    fetchCatalogMetadataMock.mockResolvedValueOnce(emptyMetadata);

    const user = await renderReady();
    expect(screen.getAllByText("選択できるスキルがありません。")).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: "必須スキルを追加" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "優先スキルを追加" }),
    ).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "検索する" }));
    expect(searchRankedBuildsMock.mock.calls[0]?.[0]).toEqual({
      requirements: [],
      preferences: [],
      max_results: 5,
    });
  });
});

describe("form", () => {
  it("adds and removes rows, prevents same-section duplicates, allows overlap, and clamps on skill change", async () => {
    const user = await renderReady();

    await user.click(screen.getByRole("button", { name: "必須スキルを追加" }));
    await user.selectOptions(
      screen.getByLabelText("必須スキル 1 のスキル"),
      "skill_attack",
    );
    await user.click(screen.getByRole("button", { name: "必須スキルを追加" }));

    const secondRequired = screen.getByLabelText("必須スキル 2 のスキル");
    expect(within(secondRequired).getByRole("option", { name: "攻撃（武器）" })).toBeDisabled();
    await user.selectOptions(secondRequired, "skill_critical_eye");

    const secondLevel = screen.getByLabelText("必須スキル 2 の最低レベル");
    fireEvent.change(secondLevel, { target: { value: "9" } });
    await user.selectOptions(secondRequired, "fallback_skill");
    expect(secondLevel).toHaveValue(3);

    await user.click(screen.getByRole("button", { name: "優先スキルを追加" }));
    const preference = screen.getByLabelText("優先スキル 1 のスキル");
    expect(within(preference).getByRole("option", { name: "攻撃（武器）" })).not.toBeDisabled();
    await user.selectOptions(preference, "skill_attack");
    expect(preference).toHaveValue("skill_attack");

    await user.click(
      screen.getAllByRole("button", { name: "必須スキルを削除" })[0]!,
    );
    expect(screen.getAllByRole("button", { name: "必須スキルを削除" })).toHaveLength(1);
  });

  it("defaults max results to 5 and disables submit for invalid max or level", async () => {
    const user = await renderReady();
    const maxResults = screen.getByLabelText("表示件数");
    const submit = screen.getByRole("button", { name: "検索する" });

    expect(maxResults).toHaveValue(5);
    expect(submit).toBeEnabled();

    await user.clear(maxResults);
    expect(submit).toBeDisabled();
    expect(screen.getByText("1から20の整数を入力してください。")).toBeInTheDocument();
    fireEvent.change(maxResults, { target: { value: "21" } });
    expect(submit).toBeDisabled();
    fireEvent.change(maxResults, { target: { value: "5" } });

    await user.click(screen.getByRole("button", { name: "必須スキルを追加" }));
    expect(submit).toBeDisabled();
    await user.selectOptions(
      screen.getByLabelText("必須スキル 1 のスキル"),
      "skill_attack",
    );
    const level = screen.getByLabelText("必須スキル 1 の最低レベル");
    fireEvent.change(level, { target: { value: "1.5" } });
    expect(submit).toBeDisabled();
    fireEvent.change(level, { target: { value: "8" } });
    expect(submit).toBeDisabled();
    fireEvent.change(level, { target: { value: "7" } });
    expect(submit).toBeEnabled();
  });

  it("sends IDs and input order in the exact payload, forwards weapon kind, and prevents duplicate submit", async () => {
    const searchRequest = deferred<RankedSearchResponse>();
    searchRankedBuildsMock.mockImplementationOnce(() => searchRequest.promise);
    const user = await renderReady();

    await user.click(screen.getByRole("button", { name: "必須スキルを追加" }));
    await user.selectOptions(
      screen.getByLabelText("必須スキル 1 のスキル"),
      "skill_attack",
    );
    fireEvent.change(screen.getByLabelText("必須スキル 1 の最低レベル"), {
      target: { value: "4" },
    });
    await user.click(screen.getByRole("button", { name: "必須スキルを追加" }));
    await user.selectOptions(
      screen.getByLabelText("必須スキル 2 のスキル"),
      "skill_critical_eye",
    );
    fireEvent.change(screen.getByLabelText("必須スキル 2 の最低レベル"), {
      target: { value: "2" },
    });

    await user.click(screen.getByRole("button", { name: "優先スキルを追加" }));
    await user.selectOptions(
      screen.getByLabelText("優先スキル 1 のスキル"),
      "skill_critical_eye",
    );
    fireEvent.change(screen.getByLabelText("優先スキル 1 の目標レベル"), {
      target: { value: "5" },
    });
    await user.selectOptions(screen.getByLabelText("武器種"), "long-sword");
    fireEvent.change(screen.getByLabelText("表示件数"), {
      target: { value: "7" },
    });

    const form = screen.getByRole("button", { name: "検索する" }).closest("form");
    expect(form).not.toBeNull();
    await user.click(screen.getByRole("button", { name: "検索する" }));

    const searchingButton = screen.getByRole("button", { name: "検索中…" });
    expect(searchingButton).toBeDisabled();
    expect(searchRankedBuildsMock).toHaveBeenCalledWith(
      {
        requirements: [
          { skill_id: "skill_attack", min_level: 4 },
          { skill_id: "skill_critical_eye", min_level: 2 },
        ],
        preferences: [
          { skill_id: "skill_critical_eye", target_level: 5 },
        ],
        max_results: 7,
        weapon_kind: "long-sword",
      },
      { signal: expect.any(AbortSignal) },
    );

    fireEvent.submit(form!);
    expect(searchRankedBuildsMock).toHaveBeenCalledTimes(1);

    await act(async () => searchRequest.resolve(EMPTY_EXHAUSTED));
    expect(
      await screen.findByText("条件を満たす装備構成が見つかりませんでした。"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("必須スキル 1 のスキル")).toHaveValue(
      "skill_attack",
    );
  });

  it("omits weapon_kind and supports empty requirements and preferences", async () => {
    const user = await renderReady();
    await user.click(screen.getByRole("button", { name: "検索する" }));

    await waitFor(() => expect(searchRankedBuildsMock).toHaveBeenCalledTimes(1));
    const payload = searchRankedBuildsMock.mock.calls[0]?.[0];
    expect(payload).toEqual({
      requirements: [],
      preferences: [],
      max_results: 5,
    });
    expect(payload).not.toHaveProperty("weapon_kind");
  });
});

describe("search states and results", () => {
  it("renders every timeout, exhausted, and result-limit status", async () => {
    const user = await renderReady();

    searchRankedBuildsMock.mockResolvedValueOnce({
      candidates: [FIRST_CANDIDATE],
      exhausted: false,
      timed_out: true,
    });
    await user.click(screen.getByRole("button", { name: "検索する" }));
    expect(
      await screen.findByText(
        "時間内に探索が完了しませんでした。見つかった候補を表示します。",
      ),
    ).toBeInTheDocument();

    searchRankedBuildsMock.mockResolvedValueOnce({
      candidates: [],
      exhausted: false,
      timed_out: true,
    });
    await user.click(await screen.findByRole("button", { name: "検索する" }));
    expect(
      await screen.findByText("時間内に候補を見つけられませんでした。"),
    ).toBeInTheDocument();

    searchRankedBuildsMock.mockResolvedValueOnce(EMPTY_EXHAUSTED);
    await user.click(await screen.findByRole("button", { name: "検索する" }));
    expect(
      await screen.findByText("条件を満たす装備構成が見つかりませんでした。"),
    ).toBeInTheDocument();

    searchRankedBuildsMock.mockResolvedValueOnce({
      candidates: [FIRST_CANDIDATE],
      exhausted: false,
      timed_out: false,
    });
    await user.click(await screen.findByRole("button", { name: "検索する" }));
    expect(
      await screen.findByText("表示上限まで候補を表示しています。"),
    ).toBeInTheDocument();
  });

  it("keeps candidate API order and renders part, ID, decoration, slot, and skill fallbacks without mutation", async () => {
    const response: RankedSearchResponse = {
      candidates: [FIRST_CANDIDATE, SECOND_CANDIDATE],
      exhausted: true,
      timed_out: false,
    };
    const originalResponse = JSON.stringify(response);
    searchRankedBuildsMock.mockResolvedValueOnce(response);
    const user = await renderReady();

    await user.click(screen.getByRole("button", { name: "検索する" }));
    expect(await screen.findByRole("heading", { name: "候補 1" })).toBeInTheDocument();

    const cards = screen.getAllByRole("article");
    expect(cards).toHaveLength(2);
    const firstCard = cards[0]!;
    const secondCard = cards[1]!;
    expect(within(firstCard).getByRole("heading", { name: "候補 1" })).toBeInTheDocument();
    expect(within(firstCard).getByText("優先スコア: 2")).toBeInTheDocument();
    expect(within(secondCard).getByRole("heading", { name: "候補 2" })).toBeInTheDocument();
    expect(within(secondCard).getByText("優先スコア: 99")).toBeInTheDocument();

    expect(
      Array.from(firstCard.querySelectorAll(".part-label"), (node) => node.textContent),
    ).toEqual(["武器", "頭", "胴", "腕", "腰", "脚", "護石"]);
    expect(within(firstCard).getByText("鉄の武器")).toBeInTheDocument();
    expect(within(firstCard).getByText("duplicate-equipment-id")).toHaveClass(
      "result-value",
    );
    expect(within(firstCard).getByText("達人珠")).toBeInTheDocument();
    expect(within(firstCard).getByText("unknown_deco")).toHaveClass(
      "result-value",
    );
    expect(within(firstCard).getByText("スロット 1")).toBeInTheDocument();
    expect(within(firstCard).getByText("スロット 3")).toBeInTheDocument();
    expect(within(firstCard).getByText("見切り")).toBeInTheDocument();
    expect(within(firstCard).getByText("unknown_skill")).toHaveClass(
      "result-value",
    );
    expect(within(firstCard).getByText("Lv. 5")).toBeInTheDocument();
    expect(within(secondCard).getByText("装飾品なし")).toBeInTheDocument();
    expect(within(secondCard).getByText("発動スキルなし")).toBeInTheDocument();
    expect(JSON.stringify(response)).toBe(originalResponse);
  });

  it("clears previous results and reports a search error", async () => {
    searchRankedBuildsMock
      .mockResolvedValueOnce({
        candidates: [FIRST_CANDIDATE],
        exhausted: true,
        timed_out: false,
      })
      .mockRejectedValueOnce(new Error("backend failure"));
    const user = await renderReady();

    await user.click(screen.getByRole("button", { name: "検索する" }));
    expect(await screen.findByRole("heading", { name: "候補 1" })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "検索する" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "検索に失敗しました。時間をおいてもう一度お試しください。",
    );
    expect(screen.queryByRole("heading", { name: "候補 1" })).not.toBeInTheDocument();
  });

  it("aborts a ranked search on unmount", async () => {
    let searchSignal: AbortSignal | undefined;
    searchRankedBuildsMock.mockImplementationOnce((_payload, options) => {
      searchSignal = options?.signal;
      return new Promise<RankedSearchResponse>(() => undefined);
    });
    const user = userEvent.setup();
    const { unmount } = render(<App />);
    await screen.findByRole("heading", { name: "装備構成を探す" });

    await user.click(screen.getByRole("button", { name: "検索する" }));
    expect(searchSignal?.aborted).toBe(false);
    unmount();
    expect(searchSignal?.aborted).toBe(true);
  });
});
