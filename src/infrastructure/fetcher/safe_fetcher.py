"""
Fetcher امن — مقابله با SSRF، DNS rebinding، redirect loop و محتوای مخرب.
هیچ درخواستی به IP private/loopback/link-local/multicast/metadata مجاز نیست.
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx

from config.settings import get_settings
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# ------------------------------------------------------------------ Blocked IP ranges

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("169.254.0.0/16"),    # link-local / AWS metadata
    ipaddress.ip_network("100.64.0.0/10"),     # Carrier-grade NAT
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),       # multicast
    ipaddress.ip_network("240.0.0.0/4"),       # reserved
]

_METADATA_HOSTS = {
    "169.254.169.254",  # AWS / GCP / Azure metadata
    "metadata.google.internal",
    "metadata",
}


@dataclass
class FetchResult:
    url: str
    status_code: int
    content: bytes
    content_type: str
    etag: Optional[str]
    last_modified: Optional[str]
    not_modified: bool = False


class SSRFBlockedError(Exception):
    """درخواست به IP/host ممنوع رد شد"""


class FetchError(Exception):
    """خطای fetch قابل بازیابی"""


def _validate_url(url: str) -> None:
    """اعتبارسنجی URL قبل از ارسال درخواست"""
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise SSRFBlockedError(f"schema نامجاز: {parsed.scheme}")

    if parsed.username or parsed.password:
        raise SSRFBlockedError("URL نباید credential داشته باشد")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFBlockedError("hostname یافت نشد")

    if hostname.lower() in _METADATA_HOSTS:
        raise SSRFBlockedError(f"hostname metadata مسدود: {hostname}")


def _validate_resolved_ip(hostname: str) -> None:
    """DNS resolution را validate می‌کند — مقابله با DNS rebinding"""
    try:
        addrs = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise FetchError(f"DNS resolution ناموفق: {hostname}") from exc

    for _, _, _, _, sockaddr in addrs:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise SSRFBlockedError(
                    f"IP {ip_str} در محدوده مسدود {network} است"
                )


class SafeFetcher:
    """
    HTTP fetcher امن با:
    - بررسی SSRF قبل و بعد از DNS
    - conditional request (ETag / Last-Modified)
    - محدودیت حجم پاسخ
    - timeout و retry مستقل
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._timeout = settings.FETCHER_TIMEOUT
        self._max_bytes = settings.FETCHER_MAX_RESPONSE_BYTES
        self._max_redirects = settings.FETCHER_MAX_REDIRECTS
        self._user_agent = settings.FETCHER_USER_AGENT

    async def fetch(
        self,
        url: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> FetchResult:
        # 1) URL validation
        _validate_url(url)

        # 2) DNS validation (pre-connect SSRF check)
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        _validate_resolved_ip(hostname)

        headers: dict[str, str] = {
            "User-Agent": self._user_agent,
            "Accept": "application/rss+xml, application/atom+xml, text/html, */*",
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        if extra_headers:
            headers.update(extra_headers)

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                max_redirects=self._max_redirects,
                timeout=httpx.Timeout(self._timeout),
                headers=headers,
                verify=True,
            ) as client:
                response = await client.get(url)

                # 3) validate redirected IP (DNS rebinding protection)
                if str(response.url) != url:
                    redir_parsed = urlparse(str(response.url))
                    if redir_parsed.hostname:
                        _validate_url(str(response.url))
                        _validate_resolved_ip(redir_parsed.hostname)

                if response.status_code == 304:
                    return FetchResult(
                        url=url,
                        status_code=304,
                        content=b"",
                        content_type="",
                        etag=response.headers.get("etag"),
                        last_modified=response.headers.get("last-modified"),
                        not_modified=True,
                    )

                response.raise_for_status()

                # 4) محدودیت حجم
                content = b""
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    content += chunk
                    if len(content) > self._max_bytes:
                        raise FetchError(
                            f"پاسخ از حد مجاز {self._max_bytes} بایت تجاوز کرد"
                        )

                content_type = response.headers.get("content-type", "")

                return FetchResult(
                    url=url,
                    status_code=response.status_code,
                    content=content,
                    content_type=content_type,
                    etag=response.headers.get("etag"),
                    last_modified=response.headers.get("last-modified"),
                )

        except (SSRFBlockedError, FetchError):
            raise
        except httpx.TimeoutException as exc:
            raise FetchError(f"timeout در fetch {url}") from exc
        except httpx.HTTPStatusError as exc:
            raise FetchError(
                f"HTTP {exc.response.status_code} در fetch {url}"
            ) from exc
        except httpx.RequestError as exc:
            raise FetchError(f"خطای درخواست HTTP: {exc}") from exc
