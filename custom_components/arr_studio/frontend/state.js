/**
 * Arr Studio frontend - persisted panel state (tab, filter, query, sort).
 */

const STORAGE_KEY = "arr_studio_state";

const DEFAULTS = { tab: "recent", kind: "all", query: "", sort: "newest" };

export function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULTS };
    const parsed = JSON.parse(raw);
    return { ...DEFAULTS, ...parsed };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage unavailable (private mode); panel still works in-memory.
  }
}
