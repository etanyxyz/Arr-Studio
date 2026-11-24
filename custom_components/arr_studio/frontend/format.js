/**
 * Arr Studio frontend - byte, speed, eta, relative time and text helpers.
 */

export function fmtBytes(n) {
  if (n === null || n === undefined) return "—";
  if (n === 0) return "0 B";
  const k = 1024;
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(k)), units.length - 1);
  return (n / Math.pow(k, i)).toFixed(1) + " " + units[i];
}

export function fmtSpeed(bps) {
  if (bps === null || bps === undefined || bps <= 0) return "—";
  const mb = bps / (1024 * 1024);
  if (mb >= 10) return Math.round(mb) + " MB/s";
  return mb.toFixed(1) + " MB/s";
}

export function fmtEta(sec) {
  if (sec === null || sec === undefined || sec <= 0) return "—";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) return h + "h " + m + "m";
  if (m > 0) return m + "m " + s + "s";
  return s + "s";
}

export function fmtRelative(iso) {
  if (!iso) return "";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  const diff = Date.now() - parsed.getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 5) return "just now";
  if (seconds < 60) return seconds + "s ago";
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return mins + "m ago";
  const hours = Math.floor(mins / 60);
  if (hours < 24) return hours + "h ago";
  const days = Math.floor(hours / 24);
  if (days < 7) return days + "d ago";
  return iso.slice(0, 10);
}

export function pct(n) {
  return Math.round(clamp01(n) * 100);
}

export function clamp01(n) {
  if (n === null || n === undefined) return 0;
  return Math.max(0, Math.min(1, n));
}

export function titleCase(text) {
  if (!text) return "";
  return text.charAt(0).toUpperCase() + text.slice(1);
}
