/**
 * Arr Studio frontend - recent additions poster grid.
 */

import { el, emptyState } from "./dom.js";
import { fmtRelative } from "./format.js";
import { lazyCover } from "./api.js";

export function renderRecent(items, loader, onOpen) {
  if (!items.length) {
    return emptyState("No recent additions");
  }
  const container = el("section", { className: "recent" });
  const grid = el("div", { className: "poster-grid" });

  for (const item of items) {
    const card = el("button", { className: "poster-card", "aria-label": item.title || "" });
    const wrap = el("div", { className: "poster-wrap" });
    const img = el("img", { className: "poster-img", alt: item.title || "" });
    if (item.poster) {
      lazyCover(img, item.poster, loader);
    } else {
      wrap.classList.add("no-cover");
      wrap.appendChild(document.createTextNode("no cover"));
    }
    wrap.appendChild(img);

    const title = el("div", { className: "card-title" }, item.title || "");
    const meta = el("div", { className: "card-meta" });
    meta.appendChild(document.createTextNode((item.kind || "") + (item.added ? " · " + fmtRelative(item.added) : "")));
    if (item.quality) {
      meta.appendChild(document.createTextNode(" · " + item.quality));
    }
    card.appendChild(wrap);
    card.appendChild(title);
    card.appendChild(meta);
    card.addEventListener("click", () => onOpen(item));
    grid.appendChild(card);
  }
  container.appendChild(grid);
  return container;
}
