/**
 * Arr Studio frontend - overview fetch and cover blob cache.
 *
 * All requests go through hass.fetchWithAuth against relative panel
 * endpoints; nothing here knows or carries credentials.
 */

const COVER_MAX = 200;
const coverCache = new Map();

export function coverPath(item, variant) {
  return (
    "/api/arr_studio/cover/" +
    item.entry_id +
    "/" +
    item.kind +
    "/" +
    item.id +
    "/" +
    variant
  );
}

export async function fetchOverview(hass) {
  const resp = await hass.fetchWithAuth("/api/arr_studio/overview", {
    cache: "no-store",
  });
  if (!resp.ok) {
    throw new Error("Overview request failed with status " + resp.status);
  }
  return resp.json();
}

export async function getCoverObjectUrl(hass, path) {
  if (coverCache.has(path)) {
    const url = coverCache.get(path);
    coverCache.delete(path);
    coverCache.set(path, url);
    return url;
  }
  const resp = await hass.fetchWithAuth(path, { cache: "no-store" });
  if (!resp.ok) {
    return null;
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  if (coverCache.size >= COVER_MAX) {
    const oldest = coverCache.keys().next().value;
    URL.revokeObjectURL(coverCache.get(oldest));
    coverCache.delete(oldest);
  }
  coverCache.set(path, url);
  return url;
}

export function lazyCover(img, path, loader) {
  img.dataset.path = path;
  const load = () => {
    loader(path).then((url) => {
      if (url) {
        img.src = url;
      }
    });
  };
  if (typeof IntersectionObserver === "function") {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            observer.unobserve(img);
            load();
          }
        }
      },
      { root: img.closest("#content"), rootMargin: "200px" },
    );
    observer.observe(img);
  } else {
    load();
  }
}

export function releaseCovers() {
  for (const url of coverCache.values()) {
    URL.revokeObjectURL(url);
  }
  coverCache.clear();
}
