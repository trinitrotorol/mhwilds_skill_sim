import { useEffect, useState } from "react";
import { profileWarnings } from "../../../../subprojects/inventory-checker/src/domain";
import { createInventoryStore } from "../../../../subprojects/inventory-checker/src/storage";
import { fetchServiceCatalog, type InventoryAcknowledgment } from "./search";

export function InventoryNotice({ onStateChange }: { onStateChange?: (state: InventoryAcknowledgment | null) => void }) {
  const [messages, setMessages] = useState<string[]>(["所持品を確認しています…"]);
  useEffect(() => {
    const store = createInventoryStore();
    const controller = new AbortController();
    let sequence = 0;
    let catalogRequest: ReturnType<typeof fetchServiceCatalog> | null = null;
    const update = async () => {
      const generation = ++sequence;
      const state = store.read();
      onStateChange?.(null);
      if (state.status !== "ready" || !state.profile) {
        setMessages([state.error ?? "所持品は未登録です。チェッカーで登録してください。"]);
        return;
      }
      try {
        // Metadata already populated the service cache. Concurrent profile
        // changes share this promise and never re-download the search index.
        catalogRequest ??= fetchServiceCatalog(controller.signal);
        const catalog = await catalogRequest;
        if (controller.signal.aborted || generation !== sequence || store.read().raw !== state.raw) return;
        setMessages([
          `所持品の保存日時: ${state.profile.updated_at}。検索開始時の保存内容を使います。`,
          ...profileWarnings(state.profile, catalog.checker),
        ]);
        if (state.raw !== null) onStateChange?.({ raw: state.raw, catalogRevision: catalog.checker.revision });
      } catch {
        catalogRequest = null;
        if (!controller.signal.aborted && generation === sequence) setMessages(["所持品とカタログの照合に失敗しました。検索条件を確認してください。"]);
      }
    };
    void update();
    const unsubscribe = store.subscribe(() => { void update(); });
    return () => { controller.abort(); unsubscribe(); store.dispose(); };
  }, [onStateChange]);
  return <ul aria-label="所持品の状態">{messages.map((message) => <li key={message}>{message}</li>)}</ul>;
}
