import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { boundedJson } from "./service/catalog";
import { EMPTY_NAMES, LOCALE_EVENT, LOCALE_KEY, LocaleContext, parseEnglishNames, readLocale, translate, type EnglishNames, type Locale } from "./i18n";

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, updateLocale] = useState<Locale>(readLocale);
  const [names, setNames] = useState<EnglishNames>(EMPTY_NAMES);
  const setLocale = useCallback((next: Locale) => {
    updateLocale(next);
    try { localStorage.setItem(LOCALE_KEY, next); } catch { /* Keep the selection for this tab when storage is blocked. */ }
    window.dispatchEvent(new CustomEvent(LOCALE_EVENT, { detail: next }));
  }, []);
  useEffect(() => {
    document.documentElement.lang = locale;
    if (!document.querySelector("title[data-service-text-ja]")) {
      document.title = translate(locale, "MHWILDS スキルシミュレータ");
    }
  }, [locale]);
  useEffect(() => {
    const storage = (event: StorageEvent) => { if (event.key === LOCALE_KEY || event.key === null) updateLocale(readLocale()); };
    const changed = (event: Event) => { const value: unknown = (event as CustomEvent).detail; if (value === "ja" || value === "en") updateLocale(value); };
    window.addEventListener("storage", storage);
    window.addEventListener(LOCALE_EVENT, changed);
    return () => { window.removeEventListener("storage", storage); window.removeEventListener(LOCALE_EVENT, changed); };
  }, []);
  useEffect(() => {
    if (locale !== "en") return;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15_000);
    void boundedJson(`${import.meta.env.BASE_URL}locales/en.json`, controller.signal, 2 * 1024 * 1024)
      .then((result) => {
        if (!controller.signal.aborted) setNames(parseEnglishNames((result as { value: unknown }).value));
      }).catch(() => { /* Unavailable translations retain the catalog's original names. */ })
      .finally(() => window.clearTimeout(timeout));
    return () => { window.clearTimeout(timeout); controller.abort(); };
  }, [locale]);
  const value = useMemo(() => ({
    locale, setLocale,
    t: (text: string) => translate(locale, text),
    name: (kind: keyof EnglishNames, id: string, fallback?: string | null) =>
      locale === "en" && Object.hasOwn(names[kind], id) ? names[kind][id]! : fallback ?? id,
  }), [locale, setLocale, names]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}
