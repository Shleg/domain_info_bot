"""DTOs for monitoring resolution and probe results."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EffectiveMonitoringSettings:
    track_http: bool
    track_https: bool
    track_ssl: bool
    track_whois: bool
    ssl_warn_days: int
    whois_warn_days: int


@dataclass
class CheckReport:
    """Raw probe results returned by ``run_full_check``."""

    http_https: dict[str, dict[str, Any]] | None
    ssl: dict[str, Any] | None
    whois: dict[str, Any] | None
