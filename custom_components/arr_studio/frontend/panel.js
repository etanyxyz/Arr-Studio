/**
 * Arr Studio frontend - panel entry module.
 *
 * Shadow-DOM custom element; all DOM is built through el() and icons are
 * parsed with DOMParser. Data comes from the authenticated overview
 * endpoint; covers load lazily through the authenticated cover endpoint.
 */

import { el, clear } from "./dom.js";
import { BASE_CSS } from "./styles.js";
import { svgIcon } from "./icons.js";
import {
  coverPath,
  fetchOverview,
  getCoverObjectUrl,
  releaseCovers,
} from "./api.js";
import { loadState, saveState } from "./state.js";
import { renderHero } from "./render-hero.js";
import { renderRecent } from "./render-recent.js";
import { renderQueue } from "./render-queue.js";
import { renderActivity } from "./render-activity.js";

const POLL_MS = 30000;
const TABS = [
  ["recent", "Recent"],
  ["downloads", "Downloads"],
  ["activity", "Activity"],
];
const FILTERS = [
  ["all", "All"],
  ["sonarr", "Sonarr"],
  ["radarr", "Radarr"],
];

class ArrStudioPanel extends HTMLElement {
  constructor() {
    super();
    this._shadow = this.attachShadow({ mode: "open" });
    this._payload = null;
    this._state = loadState();
    this._loading = false;
    this._error = null;
    this._timer = null;
    this._built = false;
    this._hass = null;
    this._tabBtns = [];
    this._kindBtns = [];
  }

  connectedCallback() {
    if (!this._built) {
      this._built = true;
      this._build();
      this._startPolling();
    }
    if (this._hass && !this._payload && !this._loading) {
      this._load();
    }
  }

  disconnectedCallback() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    releaseCovers();
    this._payload = null;
  }

  set hass(value) {
    this._hass = value;
    if (value && this._built && !this._payload && !this._loading) {
      this._load();
    }
  }

  set narrow(value) {
    this._narrow = value;
    this._shadow.host.classList.toggle("narrow", !!value);
  }

  _build() {
    const shadow = this._shadow;
    clear(shadow);
    shadow.appendChild(el("style", {}, BASE_CSS));

    const root = el("div", { id: "root" });

    const topbar = el("header", { id: "topbar" });
    const logo = el("span", { className: "logo" });
    logo.appendChild(svgIcon("film"));
    topbar.appendChild(logo);
    topbar.appendChild(el("span", { className: "topbar-title" }, "Arr Studio"));
    this._live = el("span", { className: "live" }, "Live");
    topbar.appendChild(this._live);
    topbar.appendChild(el("span", { className: "spacer" }));

    this._search = el("input", {
      className: "search",
      type: "search",
      placeholder: "Search",
      "aria-label": "Search titles",
      value: this._state.query,
    });
    this._search.addEventListener("input", (event) => {
      this._state.query = event.target.value;
      saveState(this._state);
      this._render();
    });
    topbar.appendChild(this._search);

    this._refreshBtn = el("button", { className: "icon-btn", "aria-label": "Refresh now" });
    this._refreshBtn.appendChild(svgIcon("refresh"));
    this._refreshBtn.addEventListener("click", () => this._load(true));
    topbar.appendChild(this._refreshBtn);
    root.appendChild(topbar);

    const main = el("div", { id: "main" });
    const sidebar = el("nav", { id: "sidebar" });
    const tabs = el("div", { className: "tabs" });
    for (const [tab, label] of TABS) {
      const btn = el(
        "button",
        { className: "tab" + (this._state.tab === tab ? " active" : ""), "data-tab": tab },
        label,
      );
      btn.addEventListener("click", () => {
        this._state.tab = tab;
        saveState(this._state);
        this._render();
      });
      tabs.appendChild(btn);
      this._tabBtns.push(btn);
    }
    sidebar.appendChild(tabs);

    const filters = el("div", { className: "filters" });
    for (const [kind, label] of FILTERS) {
      const btn = el(
        "button",
        { className: "filter" + (this._state.kind === kind ? " active" : ""), "data-kind": kind },
        label,
      );
      btn.addEventListener("click", () => {
        this._state.kind = kind;
        saveState(this._state);
        this._render();
      });
      filters.appendChild(btn);
      this._kindBtns.push(btn);
    }
    sidebar.appendChild(filters);
    main.appendChild(sidebar);

    this._content = el("div", { id: "content" });
    main.appendChild(this._content);
    root.appendChild(main);

    this._drawer = el("aside", { id: "detail-drawer", hidden: true });
    const closeBtn = el("button", { className: "drawer-close icon-btn", "aria-label": "Close details" });
    closeBtn.appendChild(svgIcon("close"));
    closeBtn.addEventListener("click", () => this._closeDrawer());
    this._drawer.appendChild(closeBtn);
    this._drawerBody = el("div", { className: "drawer-body" });
    this._drawer.appendChild(this._drawerBody);
    root.appendChild(this._drawer);

    shadow.appendChild(root);
  }

  _syncSidebar() {
    for (const btn of this._tabBtns) {
      btn.classList.toggle("active", btn.dataset.tab === this._state.tab);
    }
    for (const btn of this._kindBtns) {
      btn.classList.toggle("active", btn.dataset.kind === this._state.kind);
    }
  }

  _startPolling() {
    if (this._timer) {
      clearInterval(this._timer);
    }
    this._timer = setInterval(() => {
      if (document.hidden) {
        return;
      }
      this._load();
    }, POLL_MS);
  }

  _loader(path) {
    return getCoverObjectUrl(this._hass, path);
  }

  _filtered(section) {
    const items = (this._payload && this._payload[section]) || [];
    const query = this._state.query.trim().toLowerCase();
    const out = items.filter((item) => {
      if (this._state.kind !== "all" && item.kind !== this._state.kind) {
        return false;
      }
      if (query && !(item.title || "").toLowerCase().includes(query)) {
        return false;
      }
      return true;
    });
    if (section === "recent" && this._state.sort === "oldest") {
      return [...out].reverse();
    }
    return out;
  }

  _load(manual = false) {
    if (!this._hass || this._loading) {
      return;
    }
    this._loading = true;
    this._error = null;
    if (manual || !this._payload) {
      this._render();
    }
    fetchOverview(this._hass)
      .then((payload) => {
        this._payload = payload;
        this._loading = false;
        this._render();
      })
      .catch((err) => {
        this._loading = false;
        this._error = (err && err.message) || String(err);
        this._render();
      });
  }

  _render() {
    if (!this._built) {
      return;
    }
    this._syncSidebar();
    const content = this._content;
    clear(content);

    if (this._error) {
      const box = el("div", { className: "state-box" });
      box.appendChild(el("p", {}, this._error));
      const retry = el("button", { className: "btn" }, "Retry");
      retry.addEventListener("click", () => this._load(true));
      box.appendChild(retry);
      content.appendChild(box);
      this._setLive(null);
      return;
    }

    if (!this._payload) {
      if (this._loading) {
        content.appendChild(el("div", { className: "skeleton" }, "Loading…"));
      } else {
        content.appendChild(el("div", { className: "state-box" }, "Connect a server to get started."));
      }
      this._setLive(null);
      return;
    }

    content.appendChild(renderHero(this._payload));
    const loader = (path) => this._loader(path);
    const onOpen = (item) => this._openDrawer(item);
    if (this._state.tab === "recent") {
      content.appendChild(renderRecent(this._filtered("recent"), loader, onOpen));
    } else if (this._state.tab === "downloads") {
      content.appendChild(renderQueue(this._filtered("queue"), loader, onOpen));
    } else {
      content.appendChild(renderActivity(this._filtered("activity"), onOpen));
    }
    this._setLive(this._payload.servers.every((server) => server.online));
  }

  _setLive(online) {
    if (online === null) {
      this._live.textContent = "";
      this._live.classList.remove("warn");
      return;
    }
    this._live.textContent = online ? "Live" : "Degraded";
    this._live.classList.toggle("warn", !online);
  }

  async _openDrawer(item) {
    const body = this._drawerBody;
    clear(body);

    const wrap = el("div", { className: "drawer-poster" });
    const img = el("img", { className: "drawer-img", alt: item.title || "" });
    wrap.appendChild(img);
    body.appendChild(wrap);
    body.appendChild(el("h2", { className: "drawer-title" }, item.title || ""));

    const meta = el("div", { className: "drawer-meta" });
    const parts = [];
    if (item.subtitle) parts.push(item.subtitle);
    if (item.year) parts.push(String(item.year));
    if (item.quality) parts.push(item.quality);
    if (parts.length) {
      meta.appendChild(el("p", {}, parts.join(" · ")));
    }
    body.appendChild(meta);

    const tags = el("div", { className: "drawer-tags" });
    for (const tag of item.meta || []) {
      tags.appendChild(el("span", { className: "tag" }, tag));
    }
    if (tags.children.length) {
      body.appendChild(tags);
    }

    const footer = el("div", { className: "drawer-footer" });
    footer.appendChild(el("span", { className: "kind-chip" }, (item.kind || "").toUpperCase()));
    if (item.web_url) {
      const link = el(
        "a",
        { className: "drawer-link", href: item.web_url, target: "_blank", rel: "noopener noreferrer" },
        "Open in server",
      );
      footer.appendChild(link);
    }
    body.appendChild(footer);
    this._drawer.hidden = false;

    if (this._hass) {
      const posterPath = item.poster || coverPath(item, "poster");
      const fanartPath = item.fanart || coverPath(item, "fanart");
      const paths = item.poster
        ? [posterPath, fanartPath]
        : item.fanart
          ? [fanartPath, posterPath]
          : [];
      for (const path of paths) {
        const url = await getCoverObjectUrl(this._hass, path);
        if (url) {
          img.src = url;
          break;
        }
      }
    }
  }

  _closeDrawer() {
    this._drawer.hidden = true;
    clear(this._drawerBody);
  }
}

customElements.define("arr-studio-panel", ArrStudioPanel);
