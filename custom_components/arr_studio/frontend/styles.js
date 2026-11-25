/**
 * Arr Studio frontend - styles (design tokens from docs/UI.md).
 */

export const BASE_CSS = `
:host {
  display: block;
  width: 100%;
  height: 100%;
  background: #1a1a1a;
  color: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 14px;
  line-height: 1.4;
}

#root { display: flex; flex-direction: column; height: 100%; }

#topbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #212121;
  border-bottom: 1px solid #333333;
  flex: 0 0 auto;
}
.logo svg { width: 24px; height: 24px; display: block; }
.topbar-title { font-size: 16px; font-weight: 600; }
.live { font-size: 12px; color: #4caf50; }
.live.warn { color: #f44336; }
.spacer { flex: 1; }
.search {
  width: 200px;
  padding: 4px 12px;
  border-radius: 4px;
  border: 1px solid #444444;
  background: #333333;
  color: #ffffff;
}
.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #999999;
  cursor: pointer;
}
.icon-btn:hover { color: #ffffff; background: #333333; }
.icon-btn svg { width: 16px; height: 16px; }

#main { display: flex; flex: 1 1 auto; min-height: 0; }

#sidebar {
  width: 180px;
  flex: 0 0 auto;
  padding: 8px;
  border-right: 1px solid #333333;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}
.tabs { display: flex; flex-direction: column; gap: 4px; }
.tab {
  text-align: left;
  padding: 8px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #999999;
  font-size: 13px;
  cursor: pointer;
}
.tab.active { background: #333333; color: #ffffff; }
.filters { display: flex; gap: 4px; flex-wrap: wrap; }
.filter {
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid #444444;
  background: #212121;
  color: #999999;
  font-size: 12px;
  cursor: pointer;
}
.filter.active { border-color: #4285f4; color: #ffffff; }

#content {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: 16px;
  min-width: 0;
}

.hero {
  background: linear-gradient(160deg, #212121 0%, #1a1a1a 100%);
  border: 1px solid #333333;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.hero-title { font-size: 20px; font-weight: 600; margin: 0 0 8px; }
.server-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #333333;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
}
.chip.offline { opacity: 0.7; }
.chip-dot { width: 8px; height: 8px; border-radius: 50%; background: #4caf50; }
.chip-dot.down { background: #f44336; }
.chip-error { color: #f44336; }
.stats { display: flex; gap: 8px; flex-wrap: wrap; }
.stat {
  background: #212121;
  border: 1px solid #333333;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
}
.stat b { font-weight: 600; }

.poster-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 18px;
}
.poster-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  border: 1px solid #333333;
  border-radius: 8px;
  background: #212121;
  color: #ffffff;
  text-align: left;
  cursor: pointer;
}
.poster-card:hover { border-color: #4285f4; }
.poster-wrap {
  aspect-ratio: 2 / 3;
  border-radius: 4px;
  background: #333333;
  overflow: hidden;
}
.poster-wrap.no-cover { display: flex; align-items: center; justify-content: center; color: #666666; }
.poster-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.card-title { font-weight: 600; font-size: 13px; }
.card-meta { font-size: 12px; color: #999999; }

.queue-row {
  display: flex;
  gap: 8px;
  padding: 8px;
  border: 1px solid #333333;
  border-radius: 8px;
  background: #212121;
  margin-bottom: 8px;
  cursor: pointer;
}
.queue-row:hover { border-color: #4285f4; }
.queue-img { width: 48px; height: 64px; object-fit: cover; border-radius: 4px; background: #333333; }
.queue-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.queue-summary { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.queue-chip {
  padding: 2px 8px;
  border-radius: 4px;
  background: #333333;
  font-size: 12px;
  color: #999999;
}
.qc-wait { color: #ff9800; }
.qc-import { color: #4285f4; }
.qc-blocked, .qc-failed { color: #f44336; }
.qc-done { color: #4caf50; }
.queue-head { display: flex; gap: 8px; align-items: baseline; }
.queue-title { font-weight: 600; }
.queue-status { margin-left: auto; font-size: 12px; color: #999999; }
.st-wait { color: #ff9800; }
.st-import { color: #4285f4; }
.st-blocked, .st-failed { color: #f44336; }
.st-done { color: #4caf50; }
.progress { height: 4px; border-radius: 2px; background: #333333; overflow: hidden; }
.progress-fill { height: 100%; background: #4285f4; }
.queue-foot { display: flex; gap: 12px; font-size: 12px; color: #999999; }
.queue-note {
  color: #f44336;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border: 1px solid #333333;
  border-radius: 8px;
  background: #212121;
  margin-bottom: 8px;
  cursor: pointer;
}
.activity-row:hover { border-color: #4285f4; }
.activity-row svg { width: 16px; height: 16px; color: #999999; flex: 0 0 auto; }
.activity-title { font-weight: 600; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.activity-kind { font-size: 12px; color: #999999; }
.activity-date { margin-left: auto; font-size: 12px; color: #999999; }

.empty-state, .state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 16px;
  color: #999999;
  text-align: center;
}
.skeleton {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  color: #666666;
}
.btn {
  padding: 4px 12px;
  border-radius: 4px;
  border: 1px solid #4285f4;
  background: #4285f4;
  color: #ffffff;
  cursor: pointer;
}

#detail-drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: min(420px, 90vw);
  height: 100%;
  background: #212121;
  border-left: 1px solid #333333;
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.4);
  z-index: 10;
  display: flex;
  flex-direction: column;
}
#detail-drawer[hidden] { display: none; }
.drawer-close { align-self: flex-end; margin: 8px; }
.drawer-body { flex: 1; overflow-y: auto; padding: 0 16px 16px; }
.drawer-poster {
  width: 200px;
  aspect-ratio: 2 / 3;
  margin: 0 auto 16px;
  border-radius: 8px;
  overflow: hidden;
  background: #333333;
}
.drawer-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.drawer-title { font-size: 18px; margin: 0 0 8px; }
.drawer-meta p { color: #999999; margin: 0 0 8px; }
.drawer-status { font-weight: 600; font-size: 13px; margin: 0 0 8px; }
.drawer-error { color: #f44336; font-size: 12px; margin: 0 0 8px; }
.drawer-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 8px; }
.tag {
  background: #333333;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
  color: #999999;
}
.drawer-footer { display: flex; align-items: center; gap: 8px; }
.kind-chip {
  text-transform: uppercase;
  font-size: 12px;
  color: #4285f4;
}
.drawer-link { color: #4285f4; text-decoration: none; }

@media (max-width: 600px) {
  #sidebar { width: 120px; }
  .search { width: 120px; }
  .poster-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 12px; }
}
`;
