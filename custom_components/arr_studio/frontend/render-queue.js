/**
 * Arr Studio frontend - active download rows.
 */

import { el, emptyState } from "./dom.js";
import { fmtBytes, fmtEta, fmtSpeed, pct } from "./format.js";
import { lazyCover } from "./api.js";

export function renderQueue(items, loader, onOpen) {
  if (!items.length) {
    return emptyState("Nothing downloading");
  }
  const container = el("section", { className: "queue" });

  for (const item of items) {
    const row = el("div", { className: "queue-row" });
    const img = el("img", { className: "queue-img", alt: item.title || "" });
    if (item.poster) {
      lazyCover(img, item.poster, loader);
    }
    const body = el("div", { className: "queue-body" });
    const head = el("div", { className: "queue-head" });
    head.appendChild(el("span", { className: "queue-title" }, item.title || ""));
    head.appendChild(el("span", { className: "queue-status" }, item.status || "unknown"));

    const bar = el("div", { className: "progress" });
    bar.appendChild(
      el("div", { className: "progress-fill", style: { width: pct(item.progress) + "%" } }),
    );

    const foot = el("div", { className: "queue-foot" });
    foot.appendChild(el("span", {}, fmtBytes(item.size_left) + " left"));
    foot.appendChild(el("span", {}, fmtSpeed(item.speed_bps)));
    foot.appendChild(el("span", {}, "ETA " + fmtEta(item.eta_seconds)));

    body.appendChild(head);
    body.appendChild(bar);
    body.appendChild(foot);
    row.appendChild(img);
    row.appendChild(body);
    row.addEventListener("click", () => onOpen(item));
    container.appendChild(row);
  }
  return container;
}
