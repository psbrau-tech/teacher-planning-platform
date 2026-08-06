from __future__ import annotations


def required_legacy_roles(path: str) -> frozenset[str]:
    """Return the governed roles authorized for one protected legacy route."""
    if path.startswith("/api/v1/admin/costs"):
        return frozenset({"platform_admin"})
    if path.startswith("/api/v1/admin"):
        return frozenset({"school_admin", "platform_admin"})
    return frozenset({"teacher"})
