const STORAGE_KEY = "virtual_camera_client_id";

/**
 * Stable per-browser session id for virtual camera ownership (Linux deduplication).
 */
export function getOrCreateClientId(): string {
  if (typeof window === "undefined" || typeof localStorage === "undefined") {
    return "web-stub";
  }
  const existing = localStorage.getItem(STORAGE_KEY);
  if (existing && existing.trim()) {
    return existing.trim();
  }
  let id: string;
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    id = crypto.randomUUID();
  } else {
    id = `cid-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
  }
  localStorage.setItem(STORAGE_KEY, id);
  return id;
}
