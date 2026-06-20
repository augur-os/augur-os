from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse


URL_RE = re.compile(r"https?://[^\s<>\"]+")
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid"}
NOISY_HOST_PARTS = ("doubleclick.", "googleadservices.", "tracking.", "track.")
NOISY_PATH_PARTS = ("/unsubscribe", "/preferences", "/view-email", "/viewemail")
DOWNLOAD_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".tar",
    ".tgz",
    ".gz",
    ".csv",
}


@dataclass
class ClassifiedEmailLink:
    url: str
    category: str
    reason: str


@dataclass
class EmailLinkClassification:
    links: list[ClassifiedEmailLink] = field(default_factory=list)

    @property
    def article_resource_urls(self) -> list[str]:
        return [
            link.url for link in self.links if link.category == "article_resource"
        ]

    @property
    def downloadable_file_urls(self) -> list[str]:
        return [
            link.url for link in self.links if link.category == "downloadable_file"
        ]

    @property
    def skipped_links(self) -> list[ClassifiedEmailLink]:
        return [
            link for link in self.links if link.category == "unsupported_or_noisy"
        ]


def extract_urls(*values: str | None) -> list[str]:
    urls: list[str] = []
    for value in values:
        if not value:
            continue
        for match in URL_RE.findall(unescape(value)):
            cleaned = match.rstrip(").,;!?]'\"")
            normalized = _unwrap_tracking_url(cleaned)
            if normalized not in urls:
                urls.append(normalized)
    return urls


def classify_url(url: str) -> ClassifiedEmailLink:
    parsed = urlparse(url)
    host = (parsed.hostname or parsed.netloc).lower()
    path = unquote(parsed.path or "").lower()
    query = parse_qs(parsed.query)

    if not parsed.scheme or not parsed.netloc:
        return ClassifiedEmailLink(url, "unsupported_or_noisy", "invalid_url")
    if any(part in host for part in NOISY_HOST_PARTS):
        return ClassifiedEmailLink(url, "unsupported_or_noisy", "tracking_host")
    if any(part in path for part in NOISY_PATH_PARTS):
        return ClassifiedEmailLink(url, "unsupported_or_noisy", "mail_management_link")
    if _is_internal_app_link(host):
        return ClassifiedEmailLink(url, "internal_app", "internal_or_local_app")
    if any(
        key in TRACKING_QUERY_KEYS or key.startswith(TRACKING_QUERY_PREFIXES)
        for key in query
    ) and len(query) <= 2:
        return ClassifiedEmailLink(url, "unsupported_or_noisy", "tracking_only_url")
    if any(path.endswith(ext) for ext in DOWNLOAD_EXTENSIONS):
        return ClassifiedEmailLink(url, "downloadable_file", "download_extension")
    return ClassifiedEmailLink(url, "article_resource", "web_resource")


def classify_links(*values: str | None) -> EmailLinkClassification:
    return EmailLinkClassification(
        [classify_url(url) for url in extract_urls(*values)]
    )


def _unwrap_tracking_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("url", "u", "target", "redirect"):
        values = query.get(key)
        if values and values[0].startswith(("http://", "https://")):
            return values[0]
    return url


def _is_internal_app_link(host: str) -> bool:
    return (
        host in {"localhost", "127.0.0.1", "::1"}
        or host.endswith(".local")
        or host.startswith("app.")
    )
