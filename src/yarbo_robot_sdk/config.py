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

# New EMQX Dedicated cluster — used for devices that have migrated.
# Per-device migration status is queried via EMQX_MIGRATION_QUERY_URL.
# These defaults can be overridden by YarboClient constructor params or by
# /sdk/config cloud endpoint (three-tier priority resolved in ConfigProvider).
NEW_MQTT_HOST = "c4750009.ala.dedicated.aws.emqxcloud.com"
NEW_MQTT_PORT = 8883
NEW_MQTT_USE_TLS = True
EMQX_MIGRATION_QUERY_URL = (
    "https://gu7e5n9ef4.execute-api.us-east-1.amazonaws.com"
    "/Stage/yarbo/emqx-migration/query"
)
