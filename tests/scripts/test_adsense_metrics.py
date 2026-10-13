from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

from scripts import adsense_metrics as metrics


NOW = datetime(2026, 10, 7, 23, 30, tzinfo=timezone.utc)
CLIENT = {
    "client_id": "test.apps.googleusercontent.com",
    "client_secret": "private-client",
}
CREDENTIALS = {**CLIENT, "refresh_token": "private-refresh", "scope": metrics.SCOPE}


@pytest.fixture
def tmp_path():
    # The repository wrapper intentionally sets TMPDIR inside Git. Exercise the
    # real private-path guard using an OS temporary directory outside that repo.
    root = (
        Path(os.environ["LOCALAPPDATA"]) / "Temp" if os.name == "nt" else Path("/tmp")
    )
    with tempfile.TemporaryDirectory(prefix="mhwilds-metrics-test-", dir=root) as path:
        yield Path(path)


def report(domain=metrics.DOMAINS[0]):
    values = ("12.4", "30", "44", "2", "413.33333", "0.0666667", "0.9876543")
    currencies = {"ESTIMATED_EARNINGS", "PAGE_VIEWS_RPM"}
    ratios = {"PAGE_VIEWS_CTR", "AD_REQUESTS_COVERAGE"}
    return {
        "headers": [{"name": "DOMAIN_CODE", "type": "DIMENSION"}]
        + [
            {
                "name": name,
                "type": "METRIC_CURRENCY"
                if name in currencies
                else "METRIC_RATIO"
                if name in ratios
                else "METRIC_TALLY",
                **({"currencyCode": "JPY"} if name in currencies else {}),
            }
            for name in metrics.METRICS
        ],
        "rows": [
            {"cells": [{"value": domain}] + [{"value": value} for value in values]}
        ],
        "totals": {"cells": [{"value": ""}] + [{"value": value} for value in values]},
        "averages": {"cells": [{"value": ""}] + [{"value": value} for value in values]},
        "warnings": ["Recent data may be incomplete"],
        "totalMatchedRows": "1",
        "startDate": {"year": 2026, "month": 10, "day": 1},
        "endDate": {"year": 2026, "month": 10, "day": 7},
    }


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.account_pages = [
            {
                "accounts": [
                    {
                        "name": metrics.ACCOUNT,
                        "timeZone": {"id": "Asia/Tokyo"},
                        "state": "READY",
                    }
                ]
            }
        ]
        self.empty = False

    def request(self, method, url, *, headers=None, data=None):
        self.calls.append((method, url, headers, data))
        if url == metrics.TOKEN_URL:
            return {"access_token": "private-access", "scope": metrics.SCOPE}
        parsed = urlsplit(url)
        if parsed.path == "/v2/accounts":
            return self.account_pages.pop(0)
        if parsed.path.endswith("/sites"):
            return {
                "sites": [
                    {"domain": domain, "state": "READY"}
                    for domain in [*metrics.DOMAINS, "other-owner.example"]
                ]
            }
        if parsed.path.endswith("/reports:generate"):
            if self.empty:
                return {"totalMatchedRows": "0", "warnings": ["No data available"]}
            values = parse_qs(parsed.query)
            return report(values["filters"][0].split("==")[1])
        raise AssertionError("Unexpected API request")


def test_authorization_uses_readonly_offline_pkce_and_fresh_state():
    uri = "http://127.0.0.1:49123/oauth2/callback"
    url, state, verifier = metrics.authorization_request(CLIENT["client_id"], uri)
    query = parse_qs(urlsplit(url).query)
    assert query["scope"] == [metrics.SCOPE]
    assert query["access_type"] == ["offline"]
    assert query["redirect_uri"] == [uri]
    assert query["code_challenge_method"] == ["S256"]
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert query["code_challenge"] == [expected]
    assert verifier not in url and CLIENT["client_secret"] not in url
    assert state != metrics.authorization_request(CLIENT["client_id"], uri)[1]


@pytest.mark.parametrize(
    "path",
    [
        "/oauth2/callback?state=wrong&code=secret",
        "/oauth2/callback?state=%E6%97%A5%E6%9C%AC&code=secret",
        "/oauth2/callback?state=expected&state=expected&code=secret",
        "/oauth2/callback?state=expected&code=one&code=two",
        "/wrong?state=expected&code=secret",
        "/oauth2/callback?state=expected&code=",
    ],
)
def test_callback_rejects_mismatched_or_ambiguous_parameters(path):
    assert metrics.callback_result(path, "expected") is None


def test_callback_accepts_exact_state_and_redacts_denial():
    assert (
        metrics.callback_result(
            "/oauth2/callback?state=expected&code=private", "expected"
        )
        == "private"
    )
    with pytest.raises(metrics.MetricsError) as caught:
        metrics.callback_result(
            "/oauth2/callback?state=expected&error=private-error-description",
            "expected",
        )
    assert caught.value.code == "auth_denied"
    assert "private" not in str(caught.value)


def test_authorization_deadline_is_bounded_without_any_callback(monkeypatch, capsys):
    servers = []

    class FakeServer:
        def __init__(self, address, handler):
            assert address == ("127.0.0.1", 0)
            self.server_port = 49123
            self.calls = 0
            self.closed = False
            servers.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.closed = True

        def handle_request(self):
            self.calls += 1

    moments = iter((0, 0, 1, 2))
    monkeypatch.setattr(metrics, "ThreadingHTTPServer", FakeServer)
    monkeypatch.setattr(metrics.time, "monotonic", lambda: next(moments))
    with pytest.raises(metrics.MetricsError) as caught:
        metrics.authorize(CLIENT, object(), object(), timeout=2)
    assert caught.value.code == "auth_timeout"
    assert servers[0].calls == 2 and servers[0].closed
    assert servers[0].daemon_threads is True
    assert "private-client" not in capsys.readouterr().out


def test_authorization_stores_only_verified_offline_credentials(tmp_path, monkeypatch):
    output = io.StringIO()

    class FakeServer:
        def __init__(self, address, handler):
            self.server_port = 49123
            self.handler = handler

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def handle_request(self):
            url = output.getvalue().splitlines()[-1]
            state = parse_qs(urlsplit(url).query)["state"][0]
            handler = object.__new__(self.handler)
            handler.server = self
            handler.headers = {"Host": "127.0.0.1:49123"}
            handler.path = "/oauth2/callback?" + urlencode(
                {"state": state, "code": "private-code"}
            )
            handler.send_response = lambda *args: None
            handler.send_header = lambda *args: None
            handler.end_headers = lambda: None
            handler.wfile = io.BytesIO()
            handler.do_GET()

    class AuthorizationTransport(FakeTransport):
        def request(self, method, url, **kwargs):
            result = super().request(method, url, **kwargs)
            if url == metrics.TOKEN_URL:
                result["refresh_token"] = "private-refresh"
            return result

    monkeypatch.setattr(metrics, "ThreadingHTTPServer", FakeServer)
    monkeypatch.setattr(metrics.sys, "stdout", output)
    fake = AuthorizationTransport()
    store = metrics.CredentialStore(tmp_path / "state")
    result = metrics.authorize(CLIENT, store, fake)
    assert result["status"] == "authorized"
    assert store.load() == CREDENTIALS
    form = parse_qs(fake.calls[0][3].decode())
    assert form["code"] == ["private-code"]
    assert form["redirect_uri"] == ["http://127.0.0.1:49123/oauth2/callback"]
    url = output.getvalue().splitlines()[-1]
    challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(form["code_verifier"][0].encode()).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    assert parse_qs(urlsplit(url).query)["code_challenge"] == [challenge]
    assert all(
        secret not in output.getvalue()
        for secret in (
            "private-code",
            "private-client",
            "private-refresh",
            "private-access",
        )
    )


@pytest.mark.parametrize(
    "alteration",
    [
        {"token_uri": "https://attacker.example/token"},
        {"token_uri": "https://oauth2.googleapis.com/token?leak=1"},
        {"auth_uri": "https://accounts.google.com.attacker.example/auth"},
        {"client_id": "untrusted.example"},
        {"client_secret": ""},
    ],
)
def test_client_config_rejects_untrusted_endpoints(tmp_path, alteration):
    path = tmp_path / "client.json"
    path.write_text(
        json.dumps(
            {
                "installed": {
                    **CLIENT,
                    "auth_uri": metrics.AUTH_URL,
                    "token_uri": metrics.TOKEN_URL,
                    **alteration,
                }
            }
        )
    )
    with pytest.raises(metrics.MetricsError, match="Desktop app"):
        metrics.load_client_config(path)


def test_client_config_requires_desktop_and_extracts_only_credentials(tmp_path):
    path = tmp_path / "client.json"
    value = {
        **CLIENT,
        "auth_uri": metrics.AUTH_URL,
        "token_uri": metrics.TOKEN_URL,
        "redirect_uris": ["http://localhost"],
    }
    path.write_text(json.dumps({"web": value}))
    with pytest.raises(metrics.MetricsError):
        metrics.load_client_config(path)
    path.write_text(json.dumps({"installed": value}))
    assert metrics.load_client_config(path) == CLIENT


@pytest.mark.parametrize(
    "url",
    [
        "http://oauth2.googleapis.com/token",
        "https://oauth2.googleapis.com/token/",
        "https://adsense.googleapis.com.attacker.example/v2/accounts",
        "https://adsense.googleapis.com:443/v2/accounts",
        "https://adsense.googleapis.com/v2/accounts/pub-other/reports:generate",
        "https://adsense.googleapis.com/v2/accounts#fragment",
        "https://adsense.googleapis.com/v2/accounts/pub-6343181736493400/payments",
    ],
)
def test_transport_rejects_unrelated_hosts_and_resources(url):
    with pytest.raises(metrics.MetricsError, match="endpoint"):
        metrics.validate_url(url)


class ErrorOpener:
    def __init__(self, code, body):
        self.code, self.body, self.calls = code, body, 0

    def open(self, request, timeout):
        self.calls += 1
        assert timeout == 30
        raise HTTPError(
            "https://private-token-in-url.example",
            self.code,
            "private-error-message",
            {},
            io.BytesIO(json.dumps(self.body).encode()),
        )


def test_refresh_invalid_grant_requires_auth_without_exposing_response():
    opener = ErrorOpener(
        400, {"error": "invalid_grant", "error_description": "private-refresh"}
    )
    with pytest.raises(metrics.MetricsError) as caught:
        metrics.Transport(opener=opener).request(
            "POST", metrics.TOKEN_URL, data=b"private-client"
        )
    assert caught.value.code == "auth_required"
    assert "private" not in str(caught.value)
    assert opener.calls == 1


def test_get_retry_is_bounded_and_post_is_never_retried():
    opener = ErrorOpener(503, {"error": "private-token"})
    sleeps = []
    transport = metrics.Transport(opener=opener, sleep=sleeps.append)
    with pytest.raises(metrics.MetricsError):
        transport.request("GET", metrics.API_URL + "accounts")
    assert opener.calls == 3 and sleeps == [1, 2]
    with pytest.raises(metrics.MetricsError):
        transport.request("POST", metrics.TOKEN_URL)
    assert opener.calls == 4


def test_redirects_are_not_followed_or_retried():
    opener = ErrorOpener(302, {"error": "private-token"})
    with pytest.raises(metrics.MetricsError):
        metrics.Transport(opener=opener).request("POST", metrics.TOKEN_URL)
    assert opener.calls == 1
    assert (
        metrics.NoRedirect().redirect_request(
            None, None, 302, "", {}, "https://other.example"
        )
        is None
    )


def test_unexpected_token_scopes_are_rejected():
    class BroaderToken:
        def request(self, *args, **kwargs):
            return {
                "access_token": "private",
                "scope": metrics.SCOPE + " https://www.googleapis.com/auth/adsense",
            }

    with pytest.raises(metrics.MetricsError) as caught:
        metrics.token_request(BroaderToken(), {})
    assert caught.value.code == "unexpected_scope"


def test_windows_use_account_date_exclude_today_and_have_equal_previous_periods():
    windows = metrics.reporting_windows(NOW, "Asia/Tokyo")
    assert windows == {
        "last_7_days": {"start": "2026-10-01", "end": "2026-10-07"},
        "previous_7_days": {"start": "2026-09-24", "end": "2026-09-30"},
        "last_28_days": {"start": "2026-09-10", "end": "2026-10-07"},
        "previous_28_days": {"start": "2026-08-13", "end": "2026-09-09"},
    }
    assert (
        metrics.reporting_windows(NOW, "America/Los_Angeles")["last_7_days"]["end"]
        == "2026-10-06"
    )


def test_unknown_timezone_is_not_silently_assumed():
    with pytest.raises(metrics.MetricsError) as caught:
        metrics.reporting_windows(NOW, "Unknown/Timezone")
    assert caught.value.code == "timezone_unavailable"


def test_report_request_is_domain_filtered_and_period_aggregated():
    query = metrics.report_parameters(
        metrics.DOMAINS[0], {"start": "2026-10-01", "end": "2026-10-07"}
    )
    values = parse_qs(urlencode(query))
    assert values["dimensions"] == ["DOMAIN_CODE"]
    assert values["filters"] == ["DOMAIN_CODE==trinitrotorol.com"]
    assert values["metrics"] == list(metrics.METRICS)
    assert values["reportingTimeZone"] == ["ACCOUNT_TIME_ZONE"]
    assert values["endDate.day"] == ["7"]
    assert "currencyCode" not in values


def test_currency_ratios_actual_dates_warnings_and_truncation_survive():
    source = report()
    source["totalMatchedRows"] = "2"
    result = metrics.scoped_report(
        source, metrics.DOMAINS[0], {"start": "2026-10-01", "end": "2026-10-07"}
    )
    assert result["headers"][1]["currencyCode"] == "JPY"
    assert result["rows"][0]["cells"][-2]["value"] == "0.0666667"
    assert result["rows"] == source["rows"]
    assert result["totals"] == source["totals"]
    assert result["actual_end_date"] == source["endDate"]
    assert result["warnings"] == source["warnings"]
    assert result["truncated"] is True
    assert result["range_complete"] is True
    assert result["comparable"] is False


def test_incomplete_actual_dates_are_not_comparable_full_periods():
    result = metrics.scoped_report(
        report(), metrics.DOMAINS[0], {"start": "2026-09-10", "end": "2026-10-07"}
    )
    assert result["status"] == "ok"
    assert result["range_complete"] is False
    assert result["comparable"] is False


def test_foreign_host_is_never_written_as_scoped_report():
    with pytest.raises(metrics.MetricsError) as caught:
        metrics.scoped_report(report("other-owner.example"), metrics.DOMAINS[0], {})
    assert caught.value.code == "unexpected_domain"
    assert "other-owner" not in str(caught.value)


def test_empty_response_stays_empty_not_zero():
    result = metrics.scoped_report(
        {"totalMatchedRows": "0", "warnings": ["No data"]}, metrics.DOMAINS[0], {}
    )
    assert result["status"] == "empty"
    assert result["rows"] == [] and result["totals"] is None
    assert result["warnings"] == ["No data"]


def test_account_must_be_returned_exactly_by_google():
    fake = FakeTransport()
    fake.account_pages = [{"accounts": [{"name": "accounts/pub-other"}]}]
    with pytest.raises(metrics.MetricsError) as caught:
        metrics.AdSense(fake, "private").account()
    assert caught.value.code == "account_not_found"
    assert len(fake.calls) == 1


def test_account_pagination_finds_expected_account():
    fake = FakeTransport()
    fake.account_pages.insert(
        0, {"accounts": [{"name": "accounts/pub-other"}], "nextPageToken": "next"}
    )
    assert metrics.AdSense(fake, "private").account()["name"] == metrics.ACCOUNT
    assert parse_qs(urlsplit(fake.calls[1][1]).query) == {"pageToken": ["next"]}


def test_collection_filters_site_metadata_and_preserves_period_values():
    fake = FakeTransport()
    result = metrics.AdSense(fake, "private").collect(now=NOW)
    assert len(fake.calls) == 14
    assert len(result["reports"]) == 4
    assert len(result["sites"]) == 3
    assert "other-owner.example" not in json.dumps(result)
    assert "private" not in json.dumps(result)
    assert all(call[0] == "GET" for call in fake.calls)
    assert (
        result["reports"]["last_7_days"][0]["rows"][0]["cells"][-2]["value"]
        == "0.0666667"
    )


def test_collect_refreshes_without_persisting_access_token(tmp_path):
    store = metrics.CredentialStore(tmp_path / "state")
    store.save(CREDENTIALS)
    original = store.path.read_bytes()
    fake = FakeTransport()
    result = metrics.collect(store, fake, now=NOW)
    assert result["status"] == "ok"
    assert store.path.read_bytes() == original
    assert fake.calls[0][0] == "POST"
    assert parse_qs(fake.calls[0][3].decode())["grant_type"] == ["refresh_token"]


def test_private_output_rejects_git_and_published_paths(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    for path in (repo / "ignored" / "report.json", tmp_path / "dist" / "report.json"):
        with pytest.raises(metrics.MetricsError) as caught:
            metrics.atomic_private_write(path, b"private")
        assert caught.value.code == "unsafe_output"
        assert not path.exists()


@pytest.mark.skipif(os.name == "nt", reason="Unix permission and symlink assertions")
def test_private_files_are_0600_and_reject_symlink_or_permissive_credentials(tmp_path):
    store = metrics.CredentialStore(tmp_path / "private")
    store.save(CREDENTIALS)
    assert store.path.stat().st_mode & 0o777 == 0o600
    assert store.path.parent.stat().st_mode & 0o777 == 0o700
    assert store.load() == CREDENTIALS
    linked = tmp_path / "linked"
    linked.symlink_to(store.path.parent, target_is_directory=True)
    with pytest.raises(metrics.MetricsError):
        metrics.CredentialStore(linked)
    store.path.chmod(0o644)
    with pytest.raises(metrics.MetricsError) as caught:
        store.load()
    assert caught.value.code == "unsafe_credentials"


def test_status_requires_auth_without_creating_files_or_network(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.setattr(
        metrics, "Transport", lambda: pytest.fail("status must stay local")
    )
    directory = tmp_path / "new-state"
    assert metrics.main(["--state-dir", str(directory), "status"]) == 2
    assert not directory.exists()
    assert json.loads(capsys.readouterr().err)["status"] == "auth_required"


def test_failed_collect_does_not_overwrite_previous_report_or_print_secrets(
    tmp_path, capsys, monkeypatch
):
    directory = tmp_path / "private"
    store = metrics.CredentialStore(directory)
    store.save(CREDENTIALS)
    output = directory / "latest-report.json"
    metrics.atomic_private_write(output, b'{"previous": true}')
    monkeypatch.setattr(metrics, "Transport", lambda: object())

    def fail(*args, **kwargs):
        raise metrics.MetricsError(
            "auth_required", "Google authorization must be renewed."
        )

    monkeypatch.setattr(metrics, "collect", fail)
    assert metrics.main(["--state-dir", str(directory), "collect"]) == 2
    assert output.read_bytes() == b'{"previous": true}'
    captured = capsys.readouterr()
    assert "private-refresh" not in captured.err
    assert json.loads(captured.err)["status"] == "auth_required"
