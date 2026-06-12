"""EMQX migration status client — per-SN lookup against the Lambda endpoint."""

import logging

import requests

from yarbo_robot_sdk.auth import AuthManager
from yarbo_robot_sdk.config import REQUEST_TIMEOUT
from yarbo_robot_sdk.exceptions import YarboSDKError

logger = logging.getLogger(__name__)

# App-level code the Lambda returns (with HTTP 200, success=false) when the
# bearer token is missing, invalid, or expired. Triggers a refresh + one retry.
TOKEN_EXPIRED_CODE = "A0230"


class EmqxMigrationClient:
    """Queries the EMQX migration Lambda for per-SN routing decisions.

    Holds an in-memory cache keyed by SN. The cache lives for the lifetime of
    the current MQTT connection; ``YarboClient`` calls ``invalidate_all`` on
    every MQTT disconnect to force a fresh lookup on the next subscribe / publish.

    The query is authenticated with the current JWT. The stored token may be
    expired (e.g. restored from disk), so an expired-token response triggers a
    single ``AuthManager.refresh()`` + retry, mirroring ``RestClient``.

    Query failures (network, HTTP non-2xx, malformed JSON, ``success=false``)
    raise ``YarboSDKError``. Silent fallback to the legacy broker is intentionally
    avoided — falling back for an already-migrated device would connect to a
    broker the device no longer publishes to, producing a silent loss of data.
    """

    def __init__(
        self,
        query_url: str,
        auth_manager: AuthManager,
        timeout: int = REQUEST_TIMEOUT,
    ):
        self._url = query_url
        self._auth = auth_manager
        self._timeout = timeout
        self._cache: dict[str, bool] = {}

    def query(self, sn: str) -> bool:
        """Return True if the device has been migrated to the new EMQX cluster."""
        if not sn:
            raise YarboSDKError("emqx-migration query requires a non-empty sn")

        if sn in self._cache:
            return self._cache[sn]

        body = self._request(sn)

        # Expired/invalid token → refresh once and retry. A failed refresh
        # raises TokenExpiredError, which the host (HA) uses to drive reauth.
        if not body.get("success") and body.get("code") == TOKEN_EXPIRED_CODE:
            self._auth.refresh()
            body = self._request(sn)

        if not body.get("success"):
            raise YarboSDKError(
                f"emqx-migration query rejected for sn={sn}: "
                f"code={body.get('code')} msg={body.get('message')}"
            )

        data = body.get("data") or {}
        migrated = bool(data.get("migrated", False))
        self._cache[sn] = migrated
        logger.debug("emqx-migration query sn=%s -> migrated=%s", sn, migrated)
        return migrated

    def _request(self, sn: str) -> dict:
        """Perform a single authenticated query and return the parsed JSON body.

        An HTTP 401 is normalized into the app-level token-expired body so the
        caller's refresh-and-retry path handles both gateway styles uniformly.
        """
        try:
            resp = requests.get(
                self._url,
                params={"sn": sn},
                headers={"Authorization": f"Bearer {self._auth.token}"},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise YarboSDKError(
                f"emqx-migration query failed for sn={sn}: {exc}"
            ) from exc

        if resp.status_code == 401:
            return {
                "success": False,
                "code": TOKEN_EXPIRED_CODE,
                "message": resp.text,
            }

        if not resp.ok:
            raise YarboSDKError(
                f"emqx-migration query for sn={sn} returned HTTP {resp.status_code}"
            )

        try:
            return resp.json()
        except ValueError as exc:
            raise YarboSDKError(
                f"emqx-migration query for sn={sn} returned invalid JSON"
            ) from exc

    def invalidate(self, sn: str) -> None:
        """Drop the cached decision for a single SN."""
        self._cache.pop(sn, None)

    def invalidate_all(self) -> None:
        """Drop all cached decisions. Called on every MQTT disconnect."""
        self._cache.clear()
