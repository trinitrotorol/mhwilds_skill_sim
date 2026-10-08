import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "./LocaleProvider";
import { LOCALE_EVENT, LOCALE_KEY, parseEnglishNames, readLocale, translate, useLocale } from "./i18n";

function LanguageExample() {
  const { locale, setLocale, name } = useLocale();
  return <>
    <button onClick={() => setLocale(locale === "ja" ? "en" : "ja")}>{locale}</button>
    <p>{name("equipment", "equipment-id", "元の名前")}</p>
  </>;
}

beforeEach(() => { localStorage.removeItem(LOCALE_KEY); });
afterEach(() => { localStorage.removeItem(LOCALE_KEY); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("locale settings", () => {
  it("defaults invalid saved preferences to Japanese and works with blocked persistence", () => {
    localStorage.setItem(LOCALE_KEY, "other");
    expect(readLocale()).toBe("ja");
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    render(<LocaleProvider><LanguageExample /></LocaleProvider>);
    fireEvent.click(screen.getByRole("button", { name: "ja" }));
    expect(screen.getByRole("button", { name: "en" })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("en");
    expect(screen.getByText("元の名前")).toBeInTheDocument();
  });

  it("updates across tabs and same-tab events without rewriting other browser data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    localStorage.setItem("unchanged-inventory", "opaque saved profile");
    render(<LocaleProvider><LanguageExample /></LocaleProvider>);
    act(() => {
      localStorage.setItem(LOCALE_KEY, "en");
      window.dispatchEvent(new StorageEvent("storage", { key: LOCALE_KEY }));
    });
    await waitFor(() => expect(document.documentElement.lang).toBe("en"));
    act(() => { window.dispatchEvent(new CustomEvent(LOCALE_EVENT, { detail: "invalid" })); });
    expect(screen.getByRole("button", { name: "en" })).toBeInTheDocument();
    act(() => { window.dispatchEvent(new CustomEvent(LOCALE_EVENT, { detail: "ja" })); });
    expect(screen.getByRole("button", { name: "ja" })).toBeInTheDocument();
    expect(localStorage.getItem("unchanged-inventory")).toBe("opaque saved profile");
    localStorage.removeItem("unchanged-inventory");
  });

  it("ignores delayed name responses after switching back to Japanese", async () => {
    let complete!: (response: Response) => void;
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise<Response>((resolve) => { complete = resolve; })));
    render(<LocaleProvider><LanguageExample /></LocaleProvider>);
    fireEvent.click(screen.getByRole("button", { name: "ja" }));
    fireEvent.click(screen.getByRole("button", { name: "en" }));
    await act(async () => complete(new Response(JSON.stringify({ schema_version: 1, locale: "en", names: { equipment: { "equipment-id": "English name" }, skills: {}, decorations: {} } }), { headers: { "content-type": "application/json" } })));
    expect(screen.getByText("元の名前")).toBeInTheDocument();
    expect(screen.queryByText("English name")).not.toBeInTheDocument();
  });

  it("leaves production SEO titles to the static language controller", () => {
    const title = document.querySelector("title") ?? document.head.appendChild(document.createElement("title"));
    title.setAttribute("data-service-text-ja", "SEO title");
    title.textContent = "SEO title";
    try {
      render(<LocaleProvider><LanguageExample /></LocaleProvider>);
      expect(document.title).toBe("SEO title");
    } finally { title.removeAttribute("data-service-text-ja"); }
  });
});

describe("display translations", () => {
  it.each(["1,234", "1.234", "1\u202f234"])("preserves browser-localized grouping in English progress: %s", (count) => {
    const message = `4秒・${count}件探索`;
    expect(translate("en", message)).toBe(`4s · ${count} nodes explored`);
    expect(translate("ja", message)).toBe(message);
  });

  it("checks the dictionary format without treating IDs as object properties", () => {
    const dictionary = JSON.parse('{"schema_version":1,"locale":"en","names":{"skills":{"__proto__":"Safe skill"},"equipment":{},"decorations":{}}}') as unknown;
    expect(parseEnglishNames(dictionary).skills["__proto__"]).toBe("Safe skill");
    expect(() => parseEnglishNames({ schema_version: 2, locale: "en", names: {} })).toThrow();
    expect(() => parseEnglishNames({ schema_version: 1, locale: "en", names: { skills: { x: 42 }, equipment: {}, decorations: {} } })).toThrow();
  });

  it("translates domain warnings while retaining opaque IDs and unknown user labels", () => {
    expect(translate("en", "未解決の装飾品を保持: 私のスキル")).toBe("Unresolved decoration retained: 私のスキル");
    expect(translate("en", "鑑定護石 私の護石: スキルの種別またはレベルが不正です。")).toBe("Appraisal charm 私の護石: Invalid skill type or level.");
    expect(translate("en", "所持品の確認が必要です。バックアップと現在のカタログのリビジョンが異なります。 未解決の固定護石を保持: 未知の護石")).toBe("Review your inventory. The backup and current catalog have different revisions. Unresolved charm retained: 未知の護石");
    expect(translate("en", "私のスキル付き護石")).toBe("私のスキル付き護石");
    expect(translate("en", "constructor")).toBe("constructor");
  });
});
