/**
 * Arr Studio frontend - active download rows.
 */

import { el, emptyState } from "./dom.js?v=0.1.4";
import { fmtBytes, fmtEta, fmtSpeed, pct } from "./format.js?v=0.1.4";
import { lazyCover } from "./api.js?v=0.1.4";
import { queuePhase } from "./status.js?v=0.1.4";

// Phases worth summarising above the rows (downloading is the default state).
const SUMMARY_PHASES = [
  ["blocked", "import blocked"],
  ["failed", "failed"],
  ["wait", "waiting for import"],
  ["import", "importing"],
  ["done", "imported"],
];

export function renderQueue(items, loader, onOpen) {
  if (!items.length) {
    return emptyState("Nothing downloading");
  }
  const container = el("section", { className: "queue" });

  const rows = items.map((item) => ({ item, info: queuePhase(item) }));
  const counts = rows.reduce(
    (acc, row) => {
      acc[row.info.phase] = (acc[row.info.phase] || 0) + 1;
      return acc;
    },
    {},
  );
  const summary = el("div", { className: "queue-summary" });
  for (const [phase, label] of SUMMARY_PHASES) {
    if (!counts[phase]) {
      continue;
    }
    summary.appendChild(el("span", { className: "queue-chip qc-" + phase }, counts[phase] + " " + label));
  }
  if (summary.children.length) {
    container.appendChild(summary);
  }

  for (const { item, info } of rows) {
    const row = el("div", { className: "queue-row" });
    const img = el("img", { className: "queue-img", alt: item.title || "" });
    if (item.poster) {
      lazyCover(img, item.poster, loader);
    }
    const body = el("div", { className: "queue-body" });
    const head = el("div", { className: "queue-head" });
    head.appendChild(el("span", { className: "queue-title" }, item.title || ""));
    head.appendChild(el("span", { className: "queue-status st-" + info.phase }, info.label));

    const bar = el("div", { className: "progress" });
    bar.appendChild(
      el("div", { className: "progress-fill", style: { width: pct(item.progress) + "%" } }),
    );

    const foot = el("div", { className: "queue-foot" });
    foot.appendChild(el("span", {}, fmtBytes(item.size_left) + " left"));
    foot.appendChild(el("span", {}, fmtSpeed(item.speed_bps)));
    foot.appendChild(el("span", {}, "ETA " + fmtEta(item.eta_seconds)));
    if ((info.phase === "blocked" || info.phase === "failed") && item.error) {
      foot.appendChild(el("span", { className: "queue-note" }, item.error));
    }

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
