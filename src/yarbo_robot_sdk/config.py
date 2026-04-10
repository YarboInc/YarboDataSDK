"""SDK internal constants."""

# Default API base URL (Lambda endpoint)
# Override via YarboClient(api_base_url="...") for local dev/testing
DEFAULT_API_BASE_URL = "https://data-api.yarbo.ai"

# HTTP
REQUEST_TIMEOUT = 30
TOKEN_REFRESH_MAX_RETRIES = 1

# MQTT
MQTT_KEEPALIVE = 60
MQTT_RECONNECT_DELAY = 5

# Cloud config endpoint (unauthenticated)
SDK_CONFIG_ENDPOINT = "/sdk/config"
