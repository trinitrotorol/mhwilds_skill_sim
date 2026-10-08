"""Private, read-only AdSense reporting; never imported by the website build."""

from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCOPE = "https://www.googleapis.com/auth/adsense.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_URL = "https://adsense.googleapis.com/v2/"
ACCOUNT = "accounts/pub-6343181736493400"
DOMAINS = (
    "trinitrotorol.com",
    "mhwilds.trinitrotorol.com",
    "trinitrotorol.github.io",
)
METRICS = (
    "ESTIMATED_EARNINGS",
    "PAGE_VIEWS",
    "IMPRESSIONS",
    "CLICKS",
    "PAGE_VIEWS_RPM",
    "PAGE_VIEWS_CTR",
    "AD_REQUESTS_COVERAGE",
)
MAX_BODY = 10 * 1024 * 1024


class MetricsError(Exception):
    """Only fixed, non-secret messages may cross the CLI boundary."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_url(url: str) -> None:
    parsed = urlsplit(url)
    api_path = parsed.path in (
        "/v2/accounts",
        f"/v2/{ACCOUNT}/sites",
        f"/v2/{ACCOUNT}/reports:generate",
    )
    if url == TOKEN_URL:
        return
    if (
        parsed.scheme != "https"
        or parsed.netloc != "adsense.googleapis.com"
        or parsed.fragment
        or not api_path
    ):
        raise MetricsError("unsafe_endpoint", "Unexpected API endpoint rejected.")


class Transport:
    def __init__(self, *, opener=None, sleep=time.sleep):
        self.opener = opener or build_opener(NoRedirect())
        self.sleep = sleep

    def request(self, method, url, *, headers=None, data=None):
        validate_url(url)
        for attempt in range(3):
            request = Request(url, data=data, headers=headers or {}, method=method)
            try:
                with self.opener.open(request, timeout=30) as response:
                    raw = response.read(MAX_BODY + 1)
                if len(raw) > MAX_BODY:
                    raise MetricsError("invalid_response", "API response is too large.")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ValueError
                return result
            except HTTPError as exc:
                # Never surface URLs, response messages, headers, or request bodies.
                try:
                    body = json.loads(exc.read(65536))
                except (ValueError, OSError):
                    body = {}
                finally:
                    exc.close()
                if exc.code == 401 or (
                    url == TOKEN_URL
                    and isinstance(body, dict)
                    and body.get("error") == "invalid_grant"
                ):
                    raise MetricsError(
                        "auth_required", "Google authorization must be renewed."
                    ) from None
                if method == "GET" and exc.code in (429, 500, 502, 503, 504):
                    if attempt < 2:
                        self.sleep(2**attempt)
                        continue
                code = "access_denied" if exc.code == 403 else "http_error"
                raise MetricsError(
                    code, f"Google request failed (HTTP {exc.code}); no data inferred."
                ) from None
            except (URLError, TimeoutError, OSError):
                raise MetricsError(
                    "network_error", "Google request failed; no data inferred."
                ) from None
            except (ValueError, UnicodeError):
                raise MetricsError(
                    "invalid_response", "Google returned an invalid JSON response."
                ) from None
        raise AssertionError("retry loop exhausted")


def default_state_dir() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        if not root:
            raise MetricsError("state_unavailable", "LOCALAPPDATA is not configured.")
        return Path(root) / "trinitrotorol" / "site-metrics"
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "trinitrotorol" / "site-metrics"


def private_path(path: Path) -> Path:
    path = path.absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise MetricsError("unsafe_output", "Private output cannot use symbolic links.")
    path = path.resolve()
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise MetricsError("unsafe_output", "Private output must be outside Git repos.")
    if any(part.lower() in {"public", "dist", "service-assets"} for part in path.parts):
        raise MetricsError(
            "unsafe_output", "Private output cannot use published assets."
        )
    return path


def atomic_private_write(path: Path, value: bytes) -> None:
    path = private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".metrics-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def dpapi(value: bytes, *, decrypt: bool = False) -> bytes:
    """Windows CurrentUser protection, with no UI and no machine-wide key."""
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_byte))]

    buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    result = Blob()
    library = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    function = library.CryptUnprotectData if decrypt else library.CryptProtectData
    function.argtypes = [
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(Blob),
    ]
    function.restype = wintypes.BOOL
    # CRYPTPROTECT_UI_FORBIDDEN only: CurrentUser is the default scope.
    if not function(
        ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)
    ):
        raise MetricsError(
            "credential_unavailable", "Windows credential access failed."
        )
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(result.data)


class CredentialStore:
    def __init__(self, directory: Path):
        self.path = private_path(directory / "credentials.json")

    def save(self, credentials: dict) -> None:
        raw = json.dumps(credentials).encode("utf-8")
        if os.name == "nt":
            envelope = {
                "format": "windows-dpapi-current-user-v1",
                "payload": base64.b64encode(dpapi(raw)).decode("ascii"),
            }
            raw = json.dumps(envelope).encode("utf-8")
        atomic_private_write(self.path, raw)

    def load(self) -> dict:
        if not self.path.exists():
            raise MetricsError(
                "auth_required", "Run auth once before collecting reports."
            )
        private_path(self.path)
        if os.name != "nt" and self.path.stat().st_mode & 0o077:
            raise MetricsError(
                "unsafe_credentials", "Credential file must have mode 0600."
            )
        try:
            raw = self.path.read_bytes()
            if len(raw) > 65536:
                raise ValueError
            result = json.loads(raw)
            if os.name == "nt":
                if result.get("format") != "windows-dpapi-current-user-v1":
                    raise ValueError
                result = json.loads(
                    dpapi(base64.b64decode(result["payload"]), decrypt=True)
                )
            if (
                not isinstance(result, dict)
                or result.get("scope") != SCOPE
                or not all(
                    isinstance(result.get(key), str) and result[key]
                    for key in ("client_id", "client_secret", "refresh_token")
                )
            ):
                raise ValueError
            return result
        except (ValueError, KeyError, TypeError, AttributeError):
            raise MetricsError(
                "credential_unavailable", "Credentials cannot be read; authorize again."
            ) from None


def load_client_config(path: Path) -> dict:
    try:
        if path.stat().st_size > 65536:
            raise ValueError
        client = json.loads(path.read_text(encoding="utf-8"))["installed"]
        if (
            client.get("auth_uri")
            not in (AUTH_URL, "https://accounts.google.com/o/oauth2/auth")
            or client.get("token_uri") != TOKEN_URL
            or not isinstance(client.get("client_id"), str)
            or not client["client_id"].endswith(".apps.googleusercontent.com")
            or not isinstance(client.get("client_secret"), str)
            or not client["client_secret"]
        ):
            raise ValueError
        return {key: client[key] for key in ("client_id", "client_secret")}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise MetricsError(
            "invalid_client",
            "A Google Desktop app client JSON with trusted endpoints is required.",
        ) from None


def authorization_request(client_id: str, redirect_uri: str) -> tuple[str, str, str]:
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    query = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": challenge.rstrip(b"=").decode(),
        "code_challenge_method": "S256",
    }
    return AUTH_URL + "?" + urlencode(query), state, verifier


def callback_result(path: str, expected_state: str) -> str | None:
    parsed = urlsplit(path)
    if parsed.path != "/oauth2/callback" or len(path) > 16384:
        return None
    values = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=20)
    states = values.get("state", [])
    if (
        len(states) != 1
        or not states[0].isascii()
        or not hmac.compare_digest(states[0], expected_state)
    ):
        return None
    if "error" in values:
        raise MetricsError("auth_denied", "Google authorization was not granted.")
    codes = values.get("code", [])
    if len(codes) != 1 or not codes[0] or len(codes[0]) > 8192:
        return None
    return codes[0]


def token_request(transport, form: dict) -> dict:
    result = transport.request(
        "POST",
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=urlencode(form).encode("ascii"),
    )
    if result.get("scope", SCOPE).split() != [SCOPE]:
        raise MetricsError(
            "unexpected_scope", "Read-only AdSense permission is required."
        )
    if not isinstance(result.get("access_token"), str) or not result["access_token"]:
        raise MetricsError("invalid_response", "Google did not return an access token.")
    return result


def authorize(client: dict, store: CredentialStore, transport, *, timeout=300) -> dict:
    outcome = {}
    expected_state = ""

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # HTTP request targets contain authorization codes.

        def do_GET(self):
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                self.send_error(400, "Invalid callback")
                return
            try:
                code = callback_result(self.path, expected_state)
            except MetricsError as exc:
                outcome["error"] = exc
                code = None
            except ValueError:
                code = None
            if code:
                outcome["code"] = code
            content = (
                b"Authorization received. Return to the terminal."
                if code
                else b"Authorization not completed. Return to the terminal."
            )
            self.send_response(200 if code else 400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

    class CallbackServer(ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, request, client_address):
            pass  # Incomplete callbacks must not expose request details in logs.

    # A stalled callback connection must not block the main authorization deadline.
    with CallbackServer(("127.0.0.1", 0), CallbackHandler) as server:
        server.timeout = 1
        redirect_uri = f"http://127.0.0.1:{server.server_port}/oauth2/callback"
        url, expected_state, verifier = authorization_request(
            client["client_id"], redirect_uri
        )
        print(
            "Open this URL in your browser and approve read-only AdSense access:",
            flush=True,
        )
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
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if not isinstance(token.get("refresh_token"), str) or not token["refresh_token"]:
        raise MetricsError(
            "auth_required", "No offline refresh token returned; authorize again."
        )
    # Account ownership is established through accounts.list, never inferred from UI.
    account = AdSense(transport, token["access_token"]).account()
    store.save({**client, "scope": SCOPE, "refresh_token": token["refresh_token"]})
    return {"status": "authorized", "account": account["name"], "scope": SCOPE}


def account_timezone(identifier: str):
    try:
        return ZoneInfo(identifier)
    except ZoneInfoNotFoundError:
        # Native Windows stdlib may lack the IANA database. These zones have no
        # seasonal changes for the current reporting periods; never guess others.
        if identifier == "Asia/Tokyo":
            return timezone(timedelta(hours=9), "Asia/Tokyo")
        if identifier in ("UTC", "Etc/UTC"):
            return timezone.utc
        raise MetricsError(
            "timezone_unavailable",
            "The account timezone requires an IANA timezone database.",
        ) from None


def reporting_windows(now: datetime, identifier: str) -> dict:
    if now.tzinfo is None:
        raise ValueError("An aware clock is required")
    today = now.astimezone(account_timezone(identifier)).date()
    return {
        name: {
            "start": (today - timedelta(days=before)).isoformat(),
            "end": (today - timedelta(days=after)).isoformat(),
        }
        for name, before, after in (
            ("last_7_days", 7, 1),
            ("previous_7_days", 14, 8),
            ("last_28_days", 28, 1),
            ("previous_28_days", 56, 29),
        )
    }


def report_parameters(domain: str, window: dict) -> list:
    if domain not in DOMAINS:
        raise MetricsError("unexpected_domain", "Report domain is not allowlisted.")
    params = [
        ("dimensions", "DOMAIN_CODE"),
        ("filters", f"DOMAIN_CODE=={domain}"),
        ("dateRange", "CUSTOM"),
        ("reportingTimeZone", "ACCOUNT_TIME_ZONE"),
        ("languageCode", "en"),
        ("limit", "1000"),
    ]
    params.extend(("metrics", metric) for metric in METRICS)
    for prefix, value in (("startDate", window["start"]), ("endDate", window["end"])):
        date = datetime.strptime(value, "%Y-%m-%d").date()
        params.extend(
            (f"{prefix}.{part}", str(getattr(date, part)))
            for part in ("year", "month", "day")
        )
    return params


def scoped_report(result: dict, domain: str, window: dict) -> dict:
    """Keep Google's period ratios/currency/coverage; never average daily ratios."""
    headers = result.get("headers", [])
    rows = result.get("rows", [])
    if not isinstance(headers, list) or not isinstance(rows, list):
        raise MetricsError("invalid_report", "Report structure is invalid.")
    names = [header.get("name") for header in headers]
    if rows and (names != ["DOMAIN_CODE", *METRICS]):
        raise MetricsError(
            "invalid_report", "Report columns differ from the requested metrics."
        )
    for row in rows:
        cells = row.get("cells", [])
        if (
            len(cells) != len(names)
            or not cells
            or cells[0].get("value") != domain
            or domain not in DOMAINS
        ):
            # Do not write another property's rows, totals, or warnings to disk.
            raise MetricsError(
                "unexpected_domain", "Report contains an unexpected domain."
            )
    try:
        matched = int(result.get("totalMatchedRows", len(rows)))
    except (TypeError, ValueError):
        raise MetricsError("invalid_report", "Report row count is invalid.") from None
    if matched < len(rows):
        raise MetricsError("invalid_report", "Report row count is inconsistent.")

    def expected_date(value):
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
        return {part: getattr(parsed, part) for part in ("year", "month", "day")}

    range_complete = (
        bool(window.get("start"))
        and bool(window.get("end"))
        and result.get("startDate") == expected_date(window["start"])
        and result.get("endDate") == expected_date(window["end"])
    )
    return {
        "domain": domain,
        "status": "ok" if rows else "empty",
        "requested_range": window,
        "actual_start_date": result.get("startDate"),
        "actual_end_date": result.get("endDate"),
        "headers": headers,
        "rows": rows,
        "totals": result.get("totals"),
        "averages": result.get("averages"),
        "warnings": result.get("warnings", []),
        "total_matched_rows": matched,
        "returned_rows": len(rows),
        "truncated": matched > len(rows),
        "range_complete": range_complete,
        "comparable": bool(rows) and range_complete and matched == len(rows),
    }


class AdSense:
    def __init__(self, transport, access_token: str):
        self.transport = transport
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def get(self, path: str, params=()):
        url = API_URL + path
        if params:
            url += "?" + urlencode(params)
        return self.transport.request("GET", url, headers=self.headers)

    def list_items(self, path: str, key: str):
        token = None
        seen = set()
        items = []
        for _ in range(20):
            result = self.get(path, [("pageToken", token)] if token else ())
            batch = result.get(key, [])
            if not isinstance(batch, list):
                raise MetricsError(
                    "invalid_response", "Google list response is invalid."
                )
            items.extend(batch)
            token = result.get("nextPageToken")
            if not token:
                return items
            if not isinstance(token, str) or len(token) > 4096 or token in seen:
                break
            seen.add(token)
        raise MetricsError(
            "incomplete_list", "Google list pagination could not complete."
        )

    def account(self):
        matches = [
            item
            for item in self.list_items("accounts", "accounts")
            if item.get("name") == ACCOUNT
        ]
        if len(matches) != 1:
            raise MetricsError(
                "account_not_found",
                "The expected publisher account was not returned by Google.",
            )
        return matches[0]

    def collect(self, *, now: datetime) -> dict:
        account = self.account()
        identifier = account.get("timeZone", {}).get("id")
        if not isinstance(identifier, str) or not identifier:
            raise MetricsError(
                "timezone_unavailable", "Google did not return an account timezone."
            )
        windows = reporting_windows(now, identifier)
        sites = [
            {key: item.get(key) for key in ("domain", "state", "autoAdsEnabled")}
            for item in self.list_items(f"{ACCOUNT}/sites", "sites")
            if item.get("domain") in DOMAINS
        ]
        reports = {}
        for name, window in windows.items():
            reports[name] = [
                scoped_report(
                    self.get(
                        f"{ACCOUNT}/reports:generate", report_parameters(domain, window)
                    ),
                    domain,
                    window,
                )
                for domain in DOMAINS
            ]
        return {
            "schema_version": 1,
            "status": "ok",
            "collected_at": now.astimezone(timezone.utc).isoformat(),
            "account": ACCOUNT,
            "account_state": account.get("state"),
            "account_timezone": identifier,
            "sites": sites,
            "allowed_domains": list(DOMAINS),
            "metrics": list(METRICS),
            "reports": reports,
            "notes": [
                "Today is excluded in the account timezone; recent estimates may change.",
                "Empty reports mean no returned data, not zero traffic or earnings.",
                "Ratios and currency are Google's period results, not daily averages.",
                "AdSense metrics cover monetized traffic; they are not whole-site analytics.",
                "Do not compare empty, truncated, or incomplete-date reports as full periods.",
            ],
        }


def collect(store: CredentialStore, transport, *, now: datetime) -> dict:
    credentials = store.load()
    token = token_request(
        transport,
        {
            key: credentials[key]
            for key in ("client_id", "client_secret", "refresh_token")
        }
        | {"grant_type": "refresh_token"},
    )
    # Do not rewrite the durable credential on every run, or store short-lived tokens.
    return AdSense(transport, token["access_token"]).collect(now=now)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state-dir", type=Path, help="Private directory outside all Git repos"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    auth = commands.add_parser(
        "auth", help="One-time browser consent; waits up to five minutes"
    )
    auth.add_argument("--client-config", type=Path, required=True)
    commands.add_parser(
        "status", help="Local configuration check; does not contact Google"
    )
    report = commands.add_parser(
        "collect", help="Collect four private reporting periods"
    )
    report.add_argument(
        "--output", type=Path, help="Private JSON output outside all Git repos"
    )
    args = parser.parse_args(argv)
    try:
        directory = private_path(args.state_dir or default_state_dir())
        store = CredentialStore(directory)
        if args.command == "status":
            store.load()
            summary = {
                "status": "configured",
                "authorization_verified": False,
                "account": ACCOUNT,
            }
        elif args.command == "auth":
            summary = authorize(
                load_client_config(args.client_config), store, Transport()
            )
        else:
            output = private_path(args.output or directory / "latest-report.json")
            if output == store.path:
                raise MetricsError(
                    "unsafe_output", "A report cannot replace the credential file."
                )
            data = collect(store, Transport(), now=datetime.now(timezone.utc))
            atomic_private_write(
                output, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            )
            reports = [
                report for period in data["reports"].values() for report in period
            ]
            summary = {
                "status": "collected",
                "collected_at": data["collected_at"],
                "account_timezone": data["account_timezone"],
                "report_count": len(reports),
                "empty_reports": sum(report["status"] == "empty" for report in reports),
                "truncated_reports": sum(report["truncated"] for report in reports),
                "incomplete_ranges": sum(
                    not report["range_complete"] for report in reports
                ),
                "warnings": sum(len(report["warnings"]) for report in reports),
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
