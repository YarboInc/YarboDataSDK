"""Tests for EmqxMigrationClient — TC-105 ~ TC-108."""

from unittest.mock import MagicMock

import pytest
import requests
import responses

from yarbo_robot_sdk.exceptions import YarboSDKError, TokenExpiredError
from yarbo_robot_sdk.migration_client import EmqxMigrationClient, TOKEN_EXPIRED_CODE


QUERY_URL = "https://gu7e5n9ef4.execute-api.us-east-1.amazonaws.com/Stage/yarbo/emqx-migration/query"


def _ok(migrated: bool) -> dict:
    return {
        "code": "00000",
        "data": {"migrated": migrated},
        "message": "ok",
        "success": True,
        "timestamp": 1779950337310,
    }


def _failure(code: str, message: str) -> dict:
    return {
        "code": code,
        "data": {},
        "message": message,
        "success": False,
        "timestamp": 1779950337310,
    }


@pytest.fixture
def fake_auth():
    auth = MagicMock()
    auth.token = "tok-initial"
    return auth


@pytest.fixture
def migration_client(fake_auth):
    return EmqxMigrationClient(query_url=QUERY_URL, auth_manager=fake_auth, timeout=5)


class TestQuery:
    @responses.activate
    def test_query_returns_true_when_migrated(self, migration_client):
        responses.add(responses.GET, QUERY_URL, json=_ok(True), status=200)
        assert migration_client.query("SN001") is True

    @responses.activate
    def test_query_returns_false_when_not_migrated(self, migration_client):
        responses.add(responses.GET, QUERY_URL, json=_ok(False), status=200)
        assert migration_client.query("SN002") is False

    @responses.activate
    def test_query_sends_sn_as_query_param(self, migration_client):
        responses.add(responses.GET, QUERY_URL, json=_ok(True), status=200)
        migration_client.query("SN001")
        assert responses.calls[0].request.url.endswith("?sn=SN001")


class TestQueryFailures:
    """TC-105 / TC-106: failures must raise YarboSDKError, never silently fallback."""

    @responses.activate
    def test_http_5xx_raises(self, migration_client):
        responses.add(responses.GET, QUERY_URL, status=500)
        with pytest.raises(YarboSDKError, match="HTTP 500"):
            migration_client.query("SN001")
        # Cache must not be populated on failure.
        assert "SN001" not in migration_client._cache

    @responses.activate
    def test_network_error_raises(self, migration_client):
        responses.add(
            responses.GET,
            QUERY_URL,
            body=requests.exceptions.ConnectionError("dns failure"),
        )
        with pytest.raises(YarboSDKError, match="query failed for sn=SN001"):
            migration_client.query("SN001")

    @responses.activate
    def test_invalid_json_raises(self, migration_client):
        responses.add(
            responses.GET, QUERY_URL, body="not-json", status=200,
            content_type="application/json",
        )
        with pytest.raises(YarboSDKError, match="invalid JSON"):
            migration_client.query("SN001")

    @responses.activate
    def test_success_false_raises(self, migration_client):
        responses.add(
            responses.GET, QUERY_URL,
            json=_failure("B0001", "sn is empty."),
            status=200,
        )
        with pytest.raises(YarboSDKError, match="B0001.*sn is empty"):
            migration_client.query("SN001")

    def test_empty_sn_raises(self, migration_client):
        with pytest.raises(YarboSDKError, match="non-empty sn"):
            migration_client.query("")


class TestAuth:
    """Bearer token injection and expired-token refresh + retry."""

    @responses.activate
    def test_sends_bearer_token(self, migration_client, fake_auth):
        responses.add(responses.GET, QUERY_URL, json=_ok(True), status=200)
        migration_client.query("SN001")
        assert responses.calls[0].request.headers["Authorization"] == "Bearer tok-initial"

    @responses.activate
    def test_expired_code_triggers_refresh_and_retry(self, migration_client, fake_auth):
        def _refresh():
            fake_auth.token = "tok-refreshed"

        fake_auth.refresh.side_effect = _refresh
        responses.add(
            responses.GET, QUERY_URL,
            json=_failure(TOKEN_EXPIRED_CODE, "token invalid or expired."),
            status=200,
        )
        responses.add(responses.GET, QUERY_URL, json=_ok(True), status=200)

        assert migration_client.query("SN001") is True
        fake_auth.refresh.assert_called_once()
        assert len(responses.calls) == 2
        assert responses.calls[1].request.headers["Authorization"] == "Bearer tok-refreshed"

    @responses.activate
    def test_http_401_triggers_refresh_and_retry(self, migration_client, fake_auth):
        responses.add(responses.GET, QUERY_URL, status=401)
        responses.add(responses.GET, QUERY_URL, json=_ok(False), status=200)

        assert migration_client.query("SN001") is False
        fake_auth.refresh.assert_called_once()
        assert len(responses.calls) == 2

    @responses.activate
    def test_refresh_failure_propagates(self, migration_client, fake_auth):
        fake_auth.refresh.side_effect = TokenExpiredError("please login again")
        responses.add(
            responses.GET, QUERY_URL,
            json=_failure(TOKEN_EXPIRED_CODE, "token invalid or expired."),
            status=200,
        )
        with pytest.raises(TokenExpiredError):
            migration_client.query("SN001")

    @responses.activate
    def test_still_failing_after_refresh_raises(self, migration_client, fake_auth):
        responses.add(
            responses.GET, QUERY_URL,
            json=_failure(TOKEN_EXPIRED_CODE, "token invalid or expired."),
            status=200,
        )
        responses.add(
            responses.GET, QUERY_URL,
            json=_failure(TOKEN_EXPIRED_CODE, "token invalid or expired."),
            status=200,
        )
        with pytest.raises(YarboSDKError, match=f"{TOKEN_EXPIRED_CODE}.*token invalid"):
            migration_client.query("SN001")
        fake_auth.refresh.assert_called_once()


class TestCache:
    """TC-107 / TC-108: caching and invalidation."""

    @responses.activate
    def test_second_query_hits_cache(self, migration_client):
        responses.add(responses.GET, QUERY_URL, json=_ok(False), status=200)
        migration_client.query("SN001")
        migration_client.query("SN001")
        migration_client.query("SN001")
        assert len(responses.calls) == 1

    @responses.activate
    def test_invalidate_all_forces_requery(self, migration_client):
        responses.add(responses.GET, QUERY_URL, json=_ok(False), status=200)
        responses.add(responses.GET, QUERY_URL, json=_ok(True), status=200)

        assert migration_client.query("SN001") is False
        migration_client.invalidate_all()
        assert migration_client.query("SN001") is True
        assert len(responses.calls) == 2

    @responses.activate
    def test_invalidate_single_sn(self, migration_client):
        responses.add(responses.GET, QUERY_URL, json=_ok(False), status=200)
        responses.add(responses.GET, QUERY_URL, json=_ok(False), status=200)

        migration_client.query("SN001")
        migration_client.query("SN002")
        assert len(responses.calls) == 2

        migration_client.invalidate("SN001")
        # SN002 still cached, SN001 re-queried.
        responses.add(responses.GET, QUERY_URL, json=_ok(True), status=200)
        assert migration_client.query("SN002") is False  # cache hit
        assert migration_client.query("SN001") is True   # re-queried
        assert len(responses.calls) == 3
