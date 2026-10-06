import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { exportProfile, type InventoryProfile } from "../../../../subprojects/inventory-checker/src/domain";
import { createInventoryStore, INVENTORY_STORAGE_KEY } from "../../../../subprojects/inventory-checker/src/storage";
import { InventoryNotice } from "./InventoryNotice";
import { fetchServiceCatalog } from "./search";
import type { ServiceCatalog } from "./catalog";

// App tests import this component with a different service mock. Re-evaluate
// its imports when local WSL verification opts into a reused test environment.
vi.hoisted(() => { vi.resetModules(); });
vi.mock("./search", () => ({ fetchServiceCatalog: vi.fn() }));
const fetchCatalog = vi.mocked(fetchServiceCatalog);
const catalog = { checker: { schema_version: 1, revision: "revision", generated_at: "2026-10-06T00:00:00Z", skills: [], decorations: [], fixed_charms: [], appraisal_charm_skill_groups: [], appraisal_charm_patterns: [] } } as unknown as ServiceCatalog;
const profile: InventoryProfile = { schema_version: 1, profile_id: "profile", catalog_revision: "revision", updated_at: "2026-10-06T00:00:00Z", decorations: [], fixed_charms: [], appraisal_charms: [] };

beforeEach(() => { localStorage.clear(); vi.clearAllMocks(); });

describe("inventory notices", () => {
  it("shares one catalog request and only displays the latest profile after delayed loading", async () => {
    localStorage.setItem(INVENTORY_STORAGE_KEY, exportProfile(profile));
    let complete!: (value: ServiceCatalog) => void;
    fetchCatalog.mockReturnValue(new Promise((resolve) => { complete = resolve; }));
    const changed = vi.fn();
    render(<InventoryNotice onStateChange={changed} />);
    const store = createInventoryStore({ storage: localStorage, locks: null });
    await act(async () => {
      await store.write({ ...profile, decorations: [{ decoration_id: "first-unknown", quantity: 1 }] }, store.read().raw);
      await store.write({ ...profile, decorations: [{ decoration_id: "latest-unknown", quantity: 2 }] }, store.read().raw);
    });
    await act(async () => { complete(catalog); });
    expect(fetchCatalog).toHaveBeenCalledOnce();
    expect(screen.getByText(/latest-unknown/)).toBeInTheDocument();
    expect(screen.queryByText(/first-unknown/)).not.toBeInTheDocument();
    expect(changed).toHaveBeenLastCalledWith({ raw: store.read().raw, catalogRevision: "revision" });
  });

  it("does not let an older catalog response hide a newer corrupt-profile warning", async () => {
    localStorage.setItem(INVENTORY_STORAGE_KEY, exportProfile(profile));
    let complete!: (value: ServiceCatalog) => void;
    fetchCatalog.mockReturnValue(new Promise((resolve) => { complete = resolve; }));
    const changed = vi.fn();
    const { unmount } = render(<InventoryNotice onStateChange={changed} />);
    act(() => {
      localStorage.setItem(INVENTORY_STORAGE_KEY, "{broken");
      window.dispatchEvent(new StorageEvent("storage", { key: INVENTORY_STORAGE_KEY, newValue: "{broken" }));
    });
    await act(async () => { complete(catalog); });
    expect(screen.getByText(/保存データが破損/)).toBeInTheDocument();
    expect(changed).toHaveBeenLastCalledWith(null);
    unmount();
    expect(fetchCatalog.mock.calls[0]?.[0]?.aborted).toBe(true);
  });

  it("reuses the loaded catalog when further quantities change", async () => {
    localStorage.setItem(INVENTORY_STORAGE_KEY, exportProfile(profile));
    fetchCatalog.mockResolvedValue(catalog);
    const changed = vi.fn();
    render(<InventoryNotice onStateChange={changed} />);
    await waitFor(() => expect(changed).toHaveBeenLastCalledWith({ raw: exportProfile(profile), catalogRevision: "revision" }));
    const store = createInventoryStore({ storage: localStorage, locks: null });
    await act(async () => { await store.write({ ...profile, decorations: [{ decoration_id: "other-unknown", quantity: 1 }] }, store.read().raw); });
    expect(fetchCatalog).toHaveBeenCalledOnce();
    expect(screen.getByText(/other-unknown/)).toBeInTheDocument();
  });
});
