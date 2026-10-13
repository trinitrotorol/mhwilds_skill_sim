"""Collect private Search Console reports using a separate read-only grant."""

from __future__ import annotations

import argparse
import base64
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import adsense_metrics as shared

MetricsError = shared.MetricsError
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
PROPERTY = "sc-domain:trinitrotorol.com"
SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"
QUERY_URL = f"{SITES_URL}/{quote(PROPERTY, safe='')}/searchAnalytics/query"
STATE_FILE = "search-console-credentials.json"
REPORT_FILE = "search-console-latest-report.json"
SCOPES = {
    "property": None,
    "root": "trinitrotorol.com",
    "mhwilds": "mhwilds.trinitrotorol.com",
}
PERMISSIONS = {"siteOwner", "siteFullUser", "siteRestrictedUser"}
TOP_LIMIT = 100


class Transport:
    """Only token exchange, property listing and read-only analytics queries."""

    def __init__(self, *, opener=None, sleep=time.sleep):
        self.opener = opener or build_opener(shared.NoRedirect())
        self.sleep = sleep

    def request(self, method, url, *, headers=None, data=None):
        if (method, url) not in {
            ("POST", shared.TOKEN_URL),
            ("GET", SITES_URL),
            ("POST", QUERY_URL),
        }:
            raise MetricsError("unsafe_endpoint", "Unexpected API operation rejected.")
        for attempt in range(3):
            try:
                request = Request(url, data=data, headers=headers or {}, method=method)
                with self.opener.open(request, timeout=30) as response:
                    raw = response.read(shared.MAX_BODY + 1)
                if len(raw) > shared.MAX_BODY:
                    raise ValueError
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ValueError
                return result
            except HTTPError as exc:
                try:
                    body = json.loads(exc.read(65536))
                except (ValueError, OSError):
                    body = {}
                finally:
                    exc.close()
                if exc.code == 401 or (
                    url == shared.TOKEN_URL
                    and isinstance(body, dict)
                    and body.get("error") == "invalid_grant"
                ):
                    raise MetricsError(
                        "auth_required", "Search Console authorization must be renewed."
                    ) from None
                # Analytics POST is read-only; token POST is never retried.
                if (
                    url != shared.TOKEN_URL
                    and exc.code in (429, 500, 502, 503, 504)
                    and attempt < 2
                ):
                    self.sleep(2**attempt)
                    continue
                raise MetricsError(
                    "access_denied" if exc.code == 403 else "http_error",
                    f"Google request failed (HTTP {exc.code}); no data inferred.",
                ) from None
            except (URLError, OSError, TimeoutError):
                raise MetricsError(
                    "network_error", "Google request failed; no data inferred."
                ) from None
            except (ValueError, UnicodeError):
                raise MetricsError(
                    "invalid_response", "Google returned an invalid response."
                ) from None
        raise AssertionError("retry loop exhausted")


class CredentialStore(shared.CredentialStore):
    """Separate filename and scope; shared atomic write and DPAPI implementation."""

    def __init__(self, directory: Path):
        self.path = shared.private_path(directory / STATE_FILE)

    def load(self):
        if not self.path.exists():
            raise MetricsError(
                "auth_required", "Authorize Search Console before collecting reports."
            )
        shared.private_path(self.path)
        if os.name != "nt" and self.path.stat().st_mode & 0o077:
            raise MetricsError(
                "unsafe_credentials", "Credential file must have mode 0600."
            )
        try:
            if self.path.stat().st_size > 65536:
                raise ValueError
            result = json.loads(self.path.read_bytes())
            if os.name == "nt":
                if result.get("format") != "windows-dpapi-current-user-v1":
                    raise ValueError
                result = json.loads(
                    shared.dpapi(base64.b64decode(result["payload"]), decrypt=True)
                )
            if (
                not isinstance(result, dict)
                or result.get("scope") != SCOPE
                or result.get("property") != PROPERTY
                or not all(
                    isinstance(result.get(key), str) and result[key]
                    for key in ("client_id", "client_secret", "refresh_token")
                )
            ):
                raise ValueError
            return result
        except (ValueError, TypeError, KeyError, AttributeError):
            raise MetricsError(
                "credential_unavailable",
                "Search Console credentials cannot be read; authorize again.",
            ) from None


def client_from_adsense(directory: Path):
    """Reuse client registration only; never reuse the AdSense OAuth grant."""
    existing = shared.CredentialStore(directory).load()
    return {key: existing[key] for key in ("client_id", "client_secret")}


def authorization_request(client_id, redirect_uri):
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    query = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "include_granted_scopes": "false",
    }
    return shared.AUTH_URL + "?" + urlencode(query), state, verifier


def token_request(transport, form):
    token = transport.request(
        "POST",
        shared.TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=urlencode(form).encode("ascii"),
    )
    if token.get("scope", SCOPE).split() != [SCOPE]:
        raise MetricsError(
            "unexpected_scope", "Only read-only Search Console permission is accepted."
        )
    if not isinstance(token.get("access_token"), str) or not token["access_token"]:
        raise MetricsError("invalid_response", "Google did not return an access token.")
    return token


def authorize(client, store, transport, *, timeout=300):
    outcome = {}
    state = ""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def do_GET(self):
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                self.send_error(400, "Invalid callback")
                return
            try:
                code = shared.callback_result(self.path, state)
            except MetricsError as exc:
                outcome["error"] = exc
                code = None
            except ValueError:
                code = None
            if code:
                outcome["code"] = code
            body = b"Return to the terminal to check authorization."
            self.send_response(200 if code else 400)
            for name, value in {
                "Content-Type": "text/plain; charset=utf-8",
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'none'",
                "Content-Length": str(len(body)),
            }.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

    class Server(ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, request, client_address):
            pass

    with Server(("127.0.0.1", 0), Handler) as server:
        server.timeout = 1
        redirect = f"http://127.0.0.1:{server.server_port}/oauth2/callback"
        url, state, verifier = authorization_request(client["client_id"], redirect)
        print("Open this URL and approve read-only Search Console access:", flush=True)
        print(url, flush=True)
        deadline = time.monotonic() + timeout
        while not outcome and time.monotonic() < deadline:
            server.handle_request()
        if "error" in outcome:
            raise outcome["error"]
        if "code" not in outcome:
            raise MetricsError(
                "auth_timeout", "Authorization timed out; run auth again."
            )
    token = token_request(
        transport,
        {
            **client,
            "code": outcome["code"],
            "code_verifier": verifier,
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
        },
    )
    if not isinstance(token.get("refresh_token"), str) or not token["refresh_token"]:
        raise MetricsError(
            "auth_required",
            "No offline Search Console token returned; authorize again.",
        )
    site = SearchConsole(transport, token["access_token"]).site()
    store.save(
        {
            **client,
            "scope": SCOPE,
            "property": PROPERTY,
            "refresh_token": token["refresh_token"],
        }
    )
    return {
        "status": "authorized",
        "scope": SCOPE,
        "permission": site["permissionLevel"],
    }


def reporting_windows(now):
    if now.tzinfo is None:
        raise ValueError("An aware clock is required")
    try:
        today = now.astimezone(ZoneInfo("America/Los_Angeles")).date()
    except ZoneInfoNotFoundError:
        raise MetricsError(
            "timezone_unavailable",
            "Pacific reporting dates require the IANA timezone database.",
        ) from None
    # A fixed three-day lag avoids silently shifting low-traffic periods to the
    # most recent nonempty day. Final-only responses still need freshness context.
    end = today - timedelta(days=3)
    return {
        name: {
            "start": (end - timedelta(days=start)).isoformat(),
            "end": (end - timedelta(days=stop)).isoformat(),
        }
        for name, start, stop in (
            ("last_7_days", 6, 0),
            ("previous_7_days", 13, 7),
            ("last_28_days", 27, 0),
            ("previous_28_days", 55, 28),
        )
    }, today


def query_body(window, scope, dimensions=(), *, limit=TOP_LIMIT):
    if scope not in SCOPES or dimensions not in ((), ("query",), ("page",), ("date",)):
        raise MetricsError("invalid_query", "Unexpected report scope or dimensions.")
    page_based = bool(SCOPES[scope]) or "page" in dimensions
    body = {
        "startDate": window["start"],
        "endDate": window["end"],
        "type": "web",
        "dataState": "final",
        "dimensions": list(dimensions),
        "aggregationType": "auto" if page_based else "byProperty",
        "rowLimit": limit,
        "startRow": 0,
    }
    if SCOPES[scope]:
        expression = "^https?://" + SCOPES[scope].replace(".", "\\.") + "/"
        body["dimensionFilterGroups"] = [
            {
                "groupType": "and",
                "filters": [
                    {
                        "dimension": "page",
                        "operator": "includingRegex",
                        "expression": expression,
                    }
                ],
            }
        ]
    return body


def allowed_page(value, scope):
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if (
        parsed.scheme not in ("http", "https")
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 80, 443)
    ):
        return False
    if SCOPES[scope]:
        return host == SCOPES[scope]
    return host == "trinitrotorol.com" or host.endswith(".trinitrotorol.com")


def checked_result(result, body, scope):
    rows = result.get("rows", [])
    dimensions = body["dimensions"]
    if (
        not isinstance(rows, list)
        or len(rows) > body["rowLimit"]
        or (not dimensions and len(rows) > 1)
    ):
        raise MetricsError("invalid_response", "Search Console returned invalid rows.")
    retained = []
    for row in rows:
        keys = row.get("keys", [])
        if (
            not isinstance(keys, list)
            or len(keys) != len(dimensions)
            or not all(isinstance(key, str) for key in keys)
        ):
            raise MetricsError(
                "invalid_response", "Search Console returned invalid dimension keys."
            )
        values = {
            key: row.get(key) for key in ("clicks", "impressions", "ctr", "position")
        }
        if (
            not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                and value >= 0
                for value in values.values()
            )
            or values["ctr"] > 1
        ):
            raise MetricsError(
                "invalid_response", "Search Console returned invalid metric values."
            )
        if dimensions == ["page"] and not allowed_page(keys[0], scope):
            raise MetricsError(
                "unexpected_domain", "A returned page is outside the report scope."
            )
        if (
            dimensions == ["date"]
            and not body["startDate"]
            <= date.fromisoformat(keys[0]).isoformat()
            <= body["endDate"]
        ):
            raise MetricsError(
                "invalid_response", "Search Console returned an out-of-range date."
            )
        retained.append({"keys": keys, **values})
    aggregation = result.get("responseAggregationType")
    if rows and aggregation not in ("byProperty", "byPage"):
        raise MetricsError(
            "invalid_response", "Search Console did not identify its aggregation."
        )
    expected_aggregation = (
        "byPage" if body["aggregationType"] == "auto" else "byProperty"
    )
    if rows and aggregation != expected_aggregation:
        raise MetricsError(
            "invalid_response", "Search Console changed the requested aggregation."
        )
    metadata = result.get("metadata", {})
    if not isinstance(metadata, dict):
        raise MetricsError("invalid_response", "Search Console metadata is invalid.")
    is_top = dimensions in (["query"], ["page"])
    return {
        "status": "ok" if rows else "empty",
        "requested_range": {"start": body["startDate"], "end": body["endDate"]},
        "data_state": "final",
        "dimensions": dimensions,
        "rows": retained,
        "response_aggregation_type": aggregation,
        "metadata": metadata,
        "row_limit": body["rowLimit"],
        "returned_rows": len(rows),
        "row_limit_reached": is_top and len(rows) == body["rowLimit"],
        "non_exhaustive": is_top,
        "anonymous_queries_omitted": dimensions == ["query"],
        "reported_period_values": not dimensions,
        "coverage_confirmed": False,
    }


class SearchConsole:
    def __init__(self, transport, access_token):
        self.transport = transport
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def site(self):
        result = self.transport.request("GET", SITES_URL, headers=self.headers)
        entries = result.get("siteEntry", [])
        if not isinstance(entries, list):
            raise MetricsError(
                "invalid_response", "Search Console property list is invalid."
            )
        matches = [item for item in entries if item.get("siteUrl") == PROPERTY]
        if len(matches) != 1 or matches[0].get("permissionLevel") not in PERMISSIONS:
            raise MetricsError(
                "property_unavailable",
                "The expected verified Search Console property is not accessible.",
            )
        return {key: matches[0][key] for key in ("siteUrl", "permissionLevel")}

    def query(self, body, scope):
        result = self.transport.request(
            "POST",
            QUERY_URL,
            headers={**self.headers, "Content-Type": "application/json"},
            data=json.dumps(body).encode("utf-8"),
        )
        return checked_result(result, body, scope)

    def collect(self, *, now):
        site = self.site()
        windows, today = reporting_windows(now)
        probe_range = {
            "start": (today - timedelta(days=10)).isoformat(),
            "end": (today - timedelta(days=1)).isoformat(),
        }
        probe = self.query(
            query_body(probe_range, "property", ("date",), limit=10), "property"
        )
        observed = sorted(row["keys"][0] for row in probe["rows"])
        sections = {}
        for scope, host in SCOPES.items():
            periods = {}
            for name, window in windows.items():
                periods[name] = {
                    kind: self.query(
                        query_body(
                            window,
                            scope,
                            dimensions,
                            limit=1 if not dimensions else TOP_LIMIT,
                        ),
                        scope,
                    )
                    for kind, dimensions in (
                        ("overall", ()),
                        ("top_queries", ("query",)),
                        ("top_pages", ("page",)),
                    )
                }
            sections[scope] = {
                "host_filter": host,
                "overlaps_with": ["root", "mhwilds"]
                if scope == "property"
                else ["property"],
                "periods": periods,
            }
        return {
            "schema_version": 1,
            "status": "ok",
            "collected_at": now.astimezone(timezone.utc).isoformat(),
            "property": site,
            "reporting_timezone": "America/Los_Angeles",
            "search_type": "web",
            "end_date_lag_days": 3,
            "freshness": {
                "probe": probe,
                "latest_observed_final_date": observed[-1] if observed else None,
                "observed_dates": observed,
                "is_complete_through_date": False,
            },
            "sections": sections,
            "notes": [
                "Empty data is not zero traffic; reporting is delayed and dates without rows are omitted.",
                "Latest observed final date is not proof that all data through that date is complete.",
                "Property totals include every subdomain and overlap both host reports; never add these sections.",
                "Page-filtered host and property totals use different aggregation; do not reconcile by addition.",
                "Top rows are non-exhaustive even below the row limit; anonymized queries are omitted.",
                "Use overall period API values; never sum top rows or average daily CTR or position.",
                "CTR is a ratio. If recomputing comparable disjoint data, use total clicks/impressions; position requires impression weights.",
                "Compare only the same section and returned aggregation across periods; assess small sample sizes and freshness.",
                "Search Console search performance is not whole-site visits or comprehensive indexing coverage.",
            ],
        }


def collect(store, transport, *, now):
    credentials = store.load()
    token = token_request(
        transport,
        {
            key: credentials[key]
            for key in ("client_id", "client_secret", "refresh_token")
        }
        | {"grant_type": "refresh_token"},
    )
    return SearchConsole(transport, token["access_token"]).collect(now=now)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state-dir",
        type=Path,
        required=True,
        help="Explicit private state directory, outside Git",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    auth = commands.add_parser("auth")
    source = auth.add_mutually_exclusive_group(required=True)
    source.add_argument("--client-config", type=Path)
    source.add_argument(
        "--client-from-adsense-state-dir",
        type=Path,
        help="Read client registration only from existing private AdSense credentials",
    )
    commands.add_parser("status")
    commands.add_parser("collect")
    args = parser.parse_args(argv)
    try:
        directory = shared.private_path(args.state_dir)
        store = CredentialStore(directory)
        if args.command == "status":
            store.load()
            summary = {"status": "configured", "authorization_verified": False}
        elif args.command == "auth":
            client = (
                client_from_adsense(args.client_from_adsense_state_dir)
                if args.client_from_adsense_state_dir
                else shared.load_client_config(args.client_config)
            )
            summary = authorize(client, store, Transport())
        else:
            result = collect(store, Transport(), now=datetime.now(timezone.utc))
            output = shared.private_path(directory / REPORT_FILE)
            shared.atomic_private_write(
                output,
                json.dumps(
                    result, ensure_ascii=False, indent=2, allow_nan=False
                ).encode("utf-8"),
            )
            reports = [
                report
                for section in result["sections"].values()
                for period in section["periods"].values()
                for report in period.values()
            ]
            summary = {
                "status": "collected",
                "collected_at": result["collected_at"],
                "report_count": len(reports),
                "empty_reports": sum(report["status"] == "empty" for report in reports),
                "output": str(output),
            }
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except MetricsError as exc:
        print(json.dumps({"status": exc.code, "message": str(exc)}), file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        print(
            json.dumps(
                {
                    "status": "local_error",
                    "message": "Local configuration or response could not be processed; no data inferred.",
                }
            ),
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"status": "cancelled"}), file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
