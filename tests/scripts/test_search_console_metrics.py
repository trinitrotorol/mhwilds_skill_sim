from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

from scripts import search_console_metrics as script

NOW = datetime(2026, 10, 13, 7, 30, tzinfo=timezone.utc)
CLIENT = {
    "client_id": "test.apps.googleusercontent.com",
    "client_secret": "private-client",
}
CREDENTIAL = {
    **CLIENT,
    "refresh_token": "private-search-refresh",
    "scope": script.SCOPE,
    "property": script.PROPERTY,
}
WINDOW = {"start": "2026-10-04", "end": "2026-10-10"}


@pytest.fixture
def tmp_path():
    root = (
        Path(os.environ["LOCALAPPDATA"]) / "Temp" if os.name == "nt" else Path("/tmp")
    )
    with tempfile.TemporaryDirectory(prefix="mhwilds-search-test-", dir=root) as path:
        yield Path(path)


def row(keys=()):
    return {
        "keys": list(keys),
        "clicks": 3.0,
        "impressions": 20.0,
        "ctr": 0.15,
        "position": 4.75,
    }


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.permission = "siteOwner"
        self.property = script.PROPERTY
        self.empty = False
        self.bad_query = False

    def request(self, method, url, *, headers=None, data=None):
        self.calls.append((method, url, headers, data))
        if url == script.shared.TOKEN_URL:
            return {
                "access_token": "private-search-access",
                "scope": script.SCOPE,
                "refresh_token": "private-search-refresh",
            }
        if url == script.SITES_URL:
            return {
                "siteEntry": [
                    {
                        "siteUrl": "sc-domain:other-owner.example",
                        "permissionLevel": "siteOwner",
                    },
                    {"siteUrl": self.property, "permissionLevel": self.permission},
                ]
            }
        assert url == script.QUERY_URL and method == "POST"
        body = json.loads(data)
        if self.bad_query:
            raise script.MetricsError(
                "access_denied", "Google request failed (HTTP 403); no data inferred."
            )
        if self.empty:
            return {}
        dimension = body["dimensions"]
        if dimension == ["page"]:
            expression = (
                body.get("dimensionFilterGroups", [{}])[0]
                .get("filters", [{}])[0]
                .get("expression", "")
            )
            host = (
                "mhwilds.trinitrotorol.com"
                if "mhwilds" in expression
                else "trinitrotorol.com"
            )
            rows = [row([f"https://{host}/example/"])]
        elif dimension == ["query"]:
            rows = [row(["sample private query"])]
        elif dimension == ["date"]:
            rows = [row([body["startDate"]])]
        else:
            rows = [row()]
        return {
            "rows": rows,
            "responseAggregationType": "byPage"
            if body["aggregationType"] == "auto"
            else "byProperty",
        }


def test_new_grant_requests_only_readonly_search_with_pkce():
    url, state, verifier = script.authorization_request(
        CLIENT["client_id"], "http://127.0.0.1:12345/oauth2/callback"
    )
    query = parse_qs(urlsplit(url).query)
    assert query["scope"] == [script.SCOPE]
    assert query["include_granted_scopes"] == ["false"]
    assert query["access_type"] == ["offline"]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert query["code_challenge"] == [challenge]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"] == [state]
    assert verifier not in url and "private-client" not in url


def test_client_reuse_excludes_existing_adsense_refresh_and_preserves_file(tmp_path):
    old = script.shared.CredentialStore(tmp_path)
    old.save(
        {
            **CLIENT,
            "refresh_token": "private-adsense-refresh",
            "scope": script.shared.SCOPE,
        }
    )
    before = old.path.read_bytes()
    assert script.client_from_adsense(tmp_path) == CLIENT
    new = script.CredentialStore(tmp_path)
    new.save(CREDENTIAL)
    assert new.path.name == "search-console-credentials.json"
    assert old.path.read_bytes() == before
    assert new.load() == CREDENTIAL
    assert "private-adsense-refresh" not in json.dumps(new.load())


@pytest.mark.parametrize(
    "change",
    [
        {"scope": script.shared.SCOPE},
        {"property": "sc-domain:other.example"},
        {"refresh_token": ""},
    ],
)
def test_credential_requires_own_scope_and_fixed_property(tmp_path, change):
    store = script.CredentialStore(tmp_path)
    store.save({**CREDENTIAL, **change})
    with pytest.raises(script.MetricsError) as caught:
        store.load()
    assert caught.value.code == "credential_unavailable"


def test_auth_validates_property_before_saving_and_never_echoes_secrets(
    tmp_path, monkeypatch
):
    output = io.StringIO()

    class FakeServer:
        def __init__(self, address, handler):
            assert address == ("127.0.0.1", 0)
            self.server_port = 49125
            self.handler = handler

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def handle_request(self):
            query = parse_qs(urlsplit(output.getvalue().splitlines()[-1]).query)
            handler = object.__new__(self.handler)
            handler.server = self
            handler.path = "/oauth2/callback?" + urlencode(
                {"state": query["state"][0], "code": "private-code"}
            )
            handler.headers = {"Host": "127.0.0.1:49125"}
            handler.send_response = lambda *args: None
            handler.send_header = lambda *args: None
            handler.end_headers = lambda: None
            handler.wfile = io.BytesIO()
            handler.do_GET()

    monkeypatch.setattr(script, "ThreadingHTTPServer", FakeServer)
    monkeypatch.setattr(script.sys, "stdout", output)
    store = script.CredentialStore(tmp_path)
    fake = FakeTransport()
    assert script.authorize(CLIENT, store, fake)["status"] == "authorized"
    assert store.load() == CREDENTIAL
    assert fake.calls[1][1] == script.SITES_URL
    assert all(
        secret not in output.getvalue()
        for secret in (
            "private-code",
            "private-client",
            "private-search-refresh",
            "private-search-access",
        )
    )
    form = parse_qs(fake.calls[0][3].decode())
    assert form["grant_type"] == ["authorization_code"]
    assert "code_verifier" in form
    # An unverified property must not replace the existing authorized state.
    before = store.path.read_bytes()
    fake.permission = "siteUnverifiedUser"
    with pytest.raises(script.MetricsError):
        script.authorize(CLIENT, store, fake)
    assert store.path.read_bytes() == before


def test_authorization_timeout_is_bounded_without_network(monkeypatch, capsys):
    class FakeServer:
        server_port = 49125
        calls = 0

        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def handle_request(self):
            FakeServer.calls += 1

    moments = iter((0, 0, 1, 2))
    monkeypatch.setattr(script, "ThreadingHTTPServer", FakeServer)
    monkeypatch.setattr(script.time, "monotonic", lambda: next(moments))
    with pytest.raises(script.MetricsError) as caught:
        script.authorize(CLIENT, object(), object(), timeout=2)
    assert caught.value.code == "auth_timeout" and FakeServer.calls == 2
    assert "private-client" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "method,url",
    [
        ("DELETE", script.SITES_URL),
        ("PUT", script.SITES_URL),
        ("POST", script.SITES_URL),
        ("GET", script.QUERY_URL),
        ("POST", script.QUERY_URL.replace("trinitrotorol", "other-owner")),
        ("POST", script.QUERY_URL + "?key=unexpected"),
        ("GET", "https://www.googleapis.com.evil.example/webmasters/v3/sites"),
        ("POST", "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"),
    ],
)
def test_only_exact_readonly_api_operations_are_allowed(method, url):
    with pytest.raises(script.MetricsError) as caught:
        script.Transport().request(method, url)
    assert caught.value.code == "unsafe_endpoint"


class ErrorOpener:
    def __init__(self, status, body):
        self.status = status
        self.body = body
        self.calls = 0

    def open(self, request, timeout):
        self.calls += 1
        assert timeout == 30
        raise HTTPError(
            "https://private.example",
            self.status,
            "private-reason",
            {},
            io.BytesIO(json.dumps(self.body).encode()),
        )


def test_token_failure_is_redacted_and_does_not_retry():
    opener = ErrorOpener(
        400, {"error": "invalid_grant", "error_description": "private-refresh"}
    )
    with pytest.raises(script.MetricsError) as caught:
        script.Transport(opener=opener).request("POST", script.shared.TOKEN_URL)
    assert caught.value.code == "auth_required"
    assert "private" not in str(caught.value) and opener.calls == 1


def test_quota_retry_is_finite_for_readonly_post():
    opener = ErrorOpener(429, {"message": "private-query"})
    sleeps = []
    with pytest.raises(script.MetricsError):
        script.Transport(opener=opener, sleep=sleeps.append).request(
            "POST", script.QUERY_URL
        )
    assert opener.calls == 3 and sleeps == [1, 2]


def test_redirect_never_forwards_token():
    opener = ErrorOpener(302, {})
    with pytest.raises(script.MetricsError):
        script.Transport(opener=opener).request("POST", script.QUERY_URL)
    assert opener.calls == 1
    assert (
        script.shared.NoRedirect().redirect_request(
            None, None, 302, "", {}, "https://other.example"
        )
        is None
    )


@pytest.mark.parametrize(
    "scope",
    [
        script.shared.SCOPE,
        script.SCOPE + " " + script.shared.SCOPE,
        "https://www.googleapis.com/auth/webmasters",
    ],
)
def test_token_with_any_other_scope_is_not_accepted(scope):
    class Fake:
        def request(self, *args, **kwargs):
            return {"access_token": "private", "scope": scope}

    with pytest.raises(script.MetricsError) as caught:
        script.token_request(Fake(), {})
    assert caught.value.code == "unexpected_scope"


@pytest.mark.parametrize(
    "permission", ["siteOwner", "siteFullUser", "siteRestrictedUser"]
)
def test_expected_property_permission_is_preserved(permission):
    fake = FakeTransport()
    fake.permission = permission
    assert script.SearchConsole(fake, "private").site() == {
        "siteUrl": script.PROPERTY,
        "permissionLevel": permission,
    }


@pytest.mark.parametrize(
    "change",
    [{"permission": "siteUnverifiedUser"}, {"property": "https://trinitrotorol.com/"}],
)
def test_missing_or_unverified_fixed_domain_property_stops(change):
    fake = FakeTransport()
    for key, value in change.items():
        setattr(fake, key, value)
    with pytest.raises(script.MetricsError) as caught:
        script.SearchConsole(fake, "private").collect(now=NOW)
    assert caught.value.code == "property_unavailable" and len(fake.calls) == 1


def test_windows_use_pacific_dst_and_equal_nonoverlapping_comparison_periods():
    windows, today = script.reporting_windows(NOW)
    assert today.isoformat() == "2026-10-13"
    assert windows == {
        "last_7_days": {"start": "2026-10-04", "end": "2026-10-10"},
        "previous_7_days": {"start": "2026-09-27", "end": "2026-10-03"},
        "last_28_days": {"start": "2026-09-13", "end": "2026-10-10"},
        "previous_28_days": {"start": "2026-08-16", "end": "2026-09-12"},
    }
    winter, winter_day = script.reporting_windows(
        datetime(2026, 12, 13, 7, 30, tzinfo=timezone.utc)
    )
    assert winter_day.isoformat() == "2026-12-12"
    assert winter["last_7_days"]["end"] == "2026-12-09"


def test_pacific_timezone_missing_is_not_assumed_fixed_offset(monkeypatch):
    def missing(*args):
        raise script.ZoneInfoNotFoundError

    monkeypatch.setattr(script, "ZoneInfo", missing)
    with pytest.raises(script.MetricsError) as caught:
        script.reporting_windows(NOW)
    assert caught.value.code == "timezone_unavailable"


def test_host_filters_are_exact_and_force_page_aggregation():
    body = script.query_body(WINDOW, "mhwilds")
    assert body["dataState"] == "final" and body["type"] == "web"
    assert body["aggregationType"] == "auto"
    assert body["dimensionFilterGroups"][0]["filters"][0] == {
        "dimension": "page",
        "operator": "includingRegex",
        "expression": r"^https?://mhwilds\.trinitrotorol\.com/",
    }
    assert script.query_body(WINDOW, "property")["aggregationType"] == "byProperty"
    assert script.query_body(WINDOW, "property", ("page",))["aggregationType"] == "auto"


@pytest.mark.parametrize(
    "page",
    [
        "https://evil.example/",
        "https://mhwilds.trinitrotorol.com.evil.example/",
        "https://evil.example/?https://mhwilds.trinitrotorol.com/",
        "https://user@mhwilds.trinitrotorol.com/",
        "https://trinitrotorol.com/",
        "javascript:alert(1)",
    ],
)
def test_page_rows_are_checked_against_exact_host(page):
    result = {"rows": [row([page])], "responseAggregationType": "byPage"}
    with pytest.raises(script.MetricsError) as caught:
        script.checked_result(
            result, script.query_body(WINDOW, "mhwilds", ("page",)), "mhwilds"
        )
    assert caught.value.code == "unexpected_domain"


def test_property_pages_can_include_owned_subdomains_but_not_other_domains():
    assert script.allowed_page("https://another.trinitrotorol.com/page/", "property")
    assert not script.allowed_page(
        "https://trinitrotorol.com.evil.example/", "property"
    )


def test_overall_metrics_are_api_period_values_not_top_row_sums():
    fake = FakeTransport()
    result = script.SearchConsole(fake, "private").collect(now=NOW)
    assert len(fake.calls) == 38
    assert set(result["sections"]) == {"property", "root", "mhwilds"}
    overall = result["sections"]["property"]["periods"]["last_7_days"]["overall"]
    assert overall["rows"] == [row()]
    assert overall["dimensions"] == [] and overall["reported_period_values"]
    assert overall["coverage_confirmed"] is False
    assert "total" not in result
    assert result["sections"]["mhwilds"]["overlaps_with"] == ["property"]
    assert "other-owner.example" not in json.dumps(result)
    assert "private-search-access" not in json.dumps(result)


def test_top_rows_are_always_nonexhaustive_even_below_limit():
    source = {"rows": [row(["query"])], "responseAggregationType": "byProperty"}
    result = script.checked_result(
        source, script.query_body(WINDOW, "property", ("query",)), "property"
    )
    assert result["non_exhaustive"] and result["anonymous_queries_omitted"]
    assert result["row_limit_reached"] is False
    limited = script.checked_result(
        source, script.query_body(WINDOW, "property", ("query",), limit=1), "property"
    )
    assert limited["row_limit_reached"] is True


def test_empty_data_and_freshness_gaps_are_never_filled_with_zeros():
    fake = FakeTransport()
    fake.empty = True
    result = script.SearchConsole(fake, "private").collect(now=NOW)
    assert result["freshness"]["latest_observed_final_date"] is None
    assert result["freshness"]["is_complete_through_date"] is False
    overall = result["sections"]["root"]["periods"]["last_7_days"]["overall"]
    assert overall["status"] == "empty" and overall["rows"] == []
    assert overall["requested_range"] == WINDOW


def test_old_observed_final_date_does_not_shift_comparison_window():
    result = script.SearchConsole(FakeTransport(), "private").collect(now=NOW)
    assert result["freshness"]["latest_observed_final_date"] == "2026-10-03"
    overall = result["sections"]["root"]["periods"]["last_7_days"]["overall"]
    assert overall["requested_range"]["end"] == "2026-10-10"
    assert result["freshness"]["observed_dates"] == ["2026-10-03"]


def test_incomplete_metadata_is_preserved_without_claiming_coverage():
    source = {
        "rows": [row()],
        "responseAggregationType": "byProperty",
        "metadata": {"first_incomplete_date": "2026-10-08"},
    }
    result = script.checked_result(
        source, script.query_body(WINDOW, "property"), "property"
    )
    assert result["metadata"] == source["metadata"] and not result["coverage_confirmed"]


def test_changed_aggregation_and_nonfinite_metrics_are_rejected():
    body = script.query_body(WINDOW, "mhwilds")
    with pytest.raises(script.MetricsError):
        script.checked_result(
            {"rows": [row()], "responseAggregationType": "byProperty"}, body, "mhwilds"
        )
    invalid = row()
    invalid["position"] = float("nan")
    with pytest.raises(script.MetricsError):
        script.checked_result(
            {"rows": [invalid], "responseAggregationType": "byPage"}, body, "mhwilds"
        )


def test_collect_refresh_uses_only_search_console_grant(tmp_path):
    store = script.CredentialStore(tmp_path)
    store.save(CREDENTIAL)
    fake = FakeTransport()
    before = store.path.read_bytes()
    script.collect(store, fake, now=NOW)
    assert parse_qs(fake.calls[0][3].decode())["refresh_token"] == [
        "private-search-refresh"
    ]
    assert store.path.read_bytes() == before


def test_status_is_local_does_not_create_or_read_adsense_credentials(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(
        script, "Transport", lambda: pytest.fail("status must remain local")
    )
    assert script.main(["--state-dir", str(tmp_path), "status"]) == 2
    assert json.loads(capsys.readouterr().err)["status"] == "auth_required"
    assert list(tmp_path.iterdir()) == []


def test_failed_collection_keeps_last_success_and_never_writes_adsense_file(
    tmp_path, monkeypatch, capsys
):
    store = script.CredentialStore(tmp_path)
    store.save(CREDENTIAL)
    previous = tmp_path / script.REPORT_FILE
    script.shared.atomic_private_write(previous, b'{"previous": true}')
    adsense = tmp_path / "latest-report.json"
    script.shared.atomic_private_write(adsense, b'{"adsense": true}')
    fake = FakeTransport()
    fake.bad_query = True
    monkeypatch.setattr(script, "Transport", lambda: fake)
    assert script.main(["--state-dir", str(tmp_path), "collect"]) == 2
    assert previous.read_bytes() == b'{"previous": true}'
    assert adsense.read_bytes() == b'{"adsense": true}'
    assert json.loads(capsys.readouterr().err)["status"] == "access_denied"


def test_success_writes_separate_report_and_redacted_stdout(
    tmp_path, monkeypatch, capsys
):
    script.CredentialStore(tmp_path).save(CREDENTIAL)
    monkeypatch.setattr(script, "Transport", FakeTransport)
    assert script.main(["--state-dir", str(tmp_path), "collect"]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["report_count"] == 36
    assert "sample private query" not in output and "private-search" not in output
    assert (tmp_path / script.REPORT_FILE).exists()
    assert not (tmp_path / "latest-report.json").exists()


def test_private_state_must_be_outside_git(tmp_path):
    (tmp_path / ".git").mkdir()
    with pytest.raises(script.MetricsError) as caught:
        script.CredentialStore(tmp_path)
    assert caught.value.code == "unsafe_output"
