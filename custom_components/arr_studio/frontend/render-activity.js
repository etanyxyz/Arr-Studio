/**
 * Arr Studio frontend - activity feed rows.
 */

import { el, emptyState } from "./dom.js?v=0.1.4";
import { fmtRelative, titleCase } from "./format.js?v=0.1.4";
import { kindIcon } from "./icons.js?v=0.1.4";

export function renderActivity(items, onOpen) {
  if (!items.length) {
    return emptyState("No recent activity");
  }
  const container = el("section", { className: "activity" });

  for (const item of items) {
    const row = el("div", { className: "activity-row" });
    row.appendChild(kindIcon(item.kind));
    row.appendChild(el("span", { className: "activity-title" }, item.title || ""));
    row.appendChild(el("span", { className: "activity-kind" }, titleCase(item.event || "event")));
    row.appendChild(el("span", { className: "activity-date" }, fmtRelative(item.date)));
    row.addEventListener("click", () => onOpen(item));
    container.appendChild(row);
  }
  return container;
}
