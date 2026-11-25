DOMAIN = "arr_studio"
NAME = "Arr Studio"
VERSION = "0.1.3"

KIND_SONARR = "sonarr"
KIND_RADARR = "radarr"
KINDS = (KIND_SONARR, KIND_RADARR)
KIND_LABELS = {KIND_SONARR: "Sonarr", KIND_RADARR: "Radarr"}

CONF_KIND = "kind"
CONF_URL = "url"
CONF_API_KEY = "api_key"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_RECENT_LIMIT = "recent_limit"
CONF_LIBRARY_REFRESH = "library_refresh"
CONF_SHOW_UNMONITORED = "show_unmonitored"

DEFAULT_SCAN_INTERVAL = 30          # seconds, 15..600
DEFAULT_RECENT_LIMIT = 12           # 4..50 per server
DEFAULT_LIBRARY_REFRESH = 10        # minutes, 5..60
DEFAULT_VERIFY_SSL = True
DEFAULT_SHOW_UNMONITORED = False

API_PATH = "/api/v3"
REQUEST_TIMEOUT = 20

OVERVIEW_URL = "/api/arr_studio/overview"
COVER_URL_TEMPLATE = "/api/arr_studio/cover/{entry_id}/{kind}/{media_id}/{variant}"
ALLOWED_VARIANTS = ("poster", "fanart", "banner")

PANEL_URL_PATH = "arr-studio"
PANEL_ELEMENT = "arr-studio-panel"
PANEL_TITLE = "Arr Studio"
PANEL_ICON = "mdi:filmstrip-box-multiple"
FRONTEND_STATIC_URL = "/arr_studio"
FRONTEND_ENTRY = "panel.js"
DATA_FRONTEND_REGISTERED = f"{DOMAIN}_frontend_registered"
DATA_VIEWS_REGISTERED = f"{DOMAIN}_views_registered"

SERVICE_REFRESH = "refresh"

PLATFORMS = ["sensor", "binary_sensor", "image", "button"]
