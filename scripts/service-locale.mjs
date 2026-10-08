// React owns the persisted locale and <html lang>. Keep static page metadata in sync.
const root = document.documentElement;

function syncLocale() {
  const locale = root.lang === "en" ? "en" : "ja";
  for (const element of document.querySelectorAll("[data-service-text-ja]")) {
    element.textContent = element.getAttribute(`data-service-text-${locale}`);
  }
  for (const attribute of ["content", "aria-label"]) {
    for (const element of document.querySelectorAll(`[data-service-${attribute}-ja]`)) {
      element.setAttribute(attribute, element.getAttribute(`data-service-${attribute}-${locale}`));
    }
  }
}

syncLocale();
new MutationObserver(syncLocale).observe(root, { attributes: true, attributeFilter: ["lang"] });
window.addEventListener("mhwilds:locale-change", syncLocale);
