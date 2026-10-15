import { waitFor } from "@testing-library/dom";
import { expect, it } from "vitest";
import localeScript from "../../../scripts/service-locale.mjs?raw";

const japanese = "https://trinitrotorol.com/game-guide/mhwilds-guide/";
const english = "https://trinitrotorol.com/en/game-guide/mhwilds-guide/";

it.each(["ja", "en"])("keeps guide targets in sync from initial %s and preserves explicit language links", async (initial) => {
  const oldLanguage = document.documentElement.lang;
  const fixture = document.createElement("div");
  fixture.innerHTML = '<a id="localized-guide" href="' + japanese + '" data-service-href-ja="' + japanese + '" data-service-href-en="' + english + '">Guide</a>'
    + '<a id="japanese-guide" href="' + japanese + '">Japanese guide</a>'
    + '<a id="english-guide" href="' + english + '">English guide</a>';
  document.body.append(fixture);
  document.documentElement.lang = initial;
  const events = new EventTarget();
  const observers: MutationObserver[] = [];
  class ScopedObserver extends MutationObserver {
    constructor(callback: MutationCallback) {
      super(callback);
      observers.push(this);
    }
  }
  const target = () => fixture.querySelector("#localized-guide")?.getAttribute("href");
  const fixedTargets = () => [
    fixture.querySelector("#japanese-guide")?.getAttribute("href"),
    fixture.querySelector("#english-guide")?.getAttribute("href"),
  ];
  try {
    // Run the shipped module against the real DOM with isolated event subscriptions.
    new Function("document", "window", "MutationObserver", localeScript)(document, events, ScopedObserver);
    expect(target()).toBe(initial === "en" ? english : japanese);
    expect(fixedTargets()).toEqual([japanese, english]);

    document.documentElement.lang = "en";
    await waitFor(() => expect(target()).toBe(english));
    expect(fixedTargets()).toEqual([japanese, english]);

    document.documentElement.lang = "ja";
    events.dispatchEvent(new Event("mhwilds:locale-change"));
    expect(target()).toBe(japanese);
    expect(fixedTargets()).toEqual([japanese, english]);
  } finally {
    observers.forEach((observer) => observer.disconnect());
    fixture.remove();
    document.documentElement.lang = oldLanguage;
  }
});
