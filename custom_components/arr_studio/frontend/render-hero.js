/**
 * Arr Studio frontend - hero section: heading, server chips, stat pills.
 */

import { el } from "./dom.js";
import { fmtSpeed } from "./format.js";

export function renderHero(data) {
  const hero = el("section", { className: "hero" });
  hero.appendChild(el("h1", { className: "hero-title" }, "Your library, at a glance"));

  const servers = (data && data.servers) || [];

  const chips = el("div", { className: "server-chips" });
  for (const server of servers) {
    const online = !!server.online;
    const chip = el("span", { className: "chip" + (online ? "" : " offline") });
    chip.appendChild(el("span", { className: "chip-dot" + (online ? "" : " down") }));
    chip.appendChild(
      document.createTextNode((server.name || server.kind || "Arr") + " " + (server.version || "")),
    );
    if (online && server.speed_bps > 0) {
      chip.appendChild(document.createTextNode(" " + fmtSpeed(server.speed_bps)));
    }
    if (!online && server.error) {
      chip.appendChild(el("span", { className: "chip-error" }, " · " + server.error));
    }
    chips.appendChild(chip);
  }
  hero.appendChild(chips);

  const totals = servers.reduce(
    (acc, s) => {
      acc.queue += (s.counts && s.counts.queue) || 0;
      acc.downloading += (s.counts && s.counts.downloading) || 0;
      acc.recent += (s.counts && s.counts.recent) || 0;
      acc.missing += (s.counts && s.counts.missing) || 0;
      acc.library += (s.counts && s.counts.library) || 0;
      return acc;
    },
    { queue: 0, downloading: 0, recent: 0, missing: 0, library: 0 },
  );
  const stats = el("div", { className: "stats" });
  const pills = [
    ["Queue", totals.queue],
    ["Downloading", totals.downloading],
    ["Recent", totals.recent],
    ["Library", totals.library],
    ["Missing", totals.missing],
  ];
  for (const [label, value] of pills) {
    const stat = el("span", { className: "stat" });
    stat.appendChild(document.createTextNode(label + " "));
    stat.appendChild(el("b", {}, String(value)));
    stats.appendChild(stat);
  }
  hero.appendChild(stats);
  return hero;
}
