_RETIRED_LEGACY_REPLACEMENTS = {
    "/api/v1/admin/costs": "/api/v1/administration/costs",
    "/api/v1/admin/summary": "/api/v1/administration/usage",
    "/api/v1/assignments": "/api/v1/teaching-assignments",
    "/api/v1/weekly-plan": "/api/v1/plans",
}


def required_legacy_roles(path: str) -> frozenset[str]:
    """Return the governed roles authorized for one protected legacy route."""
    if path.startswith("/api/v1/admin/costs"):
        return frozenset({"platform_admin"})
    if path.startswith("/api/v1/admin"):
        return frozenset({"school_admin", "platform_admin"})
    return frozenset({"teacher"})


def retired_legacy_replacement(path: str) -> str | None:
    """Return the governed replacement for a retired synthetic production route."""
    for prefix, replacement in _RETIRED_LEGACY_REPLACEMENTS.items():
        if path.startswith(prefix):
            return replacement
    return None
