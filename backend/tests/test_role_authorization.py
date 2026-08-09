from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException

from app import administration_api
from app.auth import (
    AuthenticatedTeacher,
    require_platform_admin,
    require_school_reporting_admin,
    require_teacher,
)
from app.role_policy import required_legacy_roles, retired_legacy_replacement
from app.settings import Settings


def _identity(*roles: str) -> AuthenticatedTeacher:
    return AuthenticatedTeacher(
        subject="governed-user",
        email="governed.user@anniston.k12.al.us",
        display_name="Governed User",
        school_id="school-1",
        roles=frozenset(roles),
        access_token="test-token",
    )


def test_teacher_role_is_required_for_teacher_workflows() -> None:
    assert require_teacher(_identity("teacher")).roles == frozenset({"teacher"})

    with pytest.raises(HTTPException) as error:
        require_teacher(_identity("school_admin"))

    assert error.value.status_code == 403


def test_reporting_allows_school_district_or_platform_administrator() -> None:
    assert require_school_reporting_admin(_identity("school_admin"))
    assert require_school_reporting_admin(_identity("district_admin"))
    assert require_school_reporting_admin(_identity("platform_admin"))

    with pytest.raises(HTTPException) as error:
        require_school_reporting_admin(_identity("teacher"))

    assert error.value.status_code == 403


def test_cost_reporting_requires_platform_administrator() -> None:
    assert require_platform_admin(_identity("platform_admin"))

    for denied_role in ("school_admin", "district_admin", "teacher"):
        with pytest.raises(HTTPException) as error:
            require_platform_admin(_identity(denied_role))
        assert error.value.status_code == 403


def test_legacy_route_roles_are_explicit() -> None:
    assert required_legacy_roles("/api/v1/admin/costs") == frozenset({"platform_admin"})
    assert required_legacy_roles("/api/v1/admin/summary") == frozenset(
        {"school_admin", "district_admin", "platform_admin"}
    )
    assert required_legacy_roles(
        "/api/v1/documents/anniston-hqi-packet"
    ) == frozenset({"teacher"})


def test_synthetic_legacy_routes_have_governed_replacements() -> None:
    assert retired_legacy_replacement("/api/v1/assignments") == (
        "/api/v1/teaching-assignments"
    )
    assert retired_legacy_replacement("/api/v1/weekly-plan?level=LET%201") == (
        "/api/v1/plans"
    )
    assert retired_legacy_replacement("/api/v1/admin/summary") == (
        "/api/v1/administration/usage"
    )
    assert retired_legacy_replacement("/api/v1/admin/costs") == (
        "/api/v1/administration/costs"
    )
    assert retired_legacy_replacement("/api/v1/documents/anniston-hqi-packet") is None


class _FakeReportingClient:
    def request(
        self,
        method: str,
        resource: str,
        *,
        params: dict[str, str] | None = None,
        payload: dict[str, object] | list[dict[str, object]] | None = None,
        prefer: str | None = None,
    ) -> object:
        del method, params, prefer
        if resource == "school_admin_usage_summary":
            return [
                {
                    "school_id": "school-1",
                    "teachers_configured": 4,
                    "teachers_with_assignments": 3,
                    "assignments_configured": 7,
                    "weekly_plans_created": 6,
                    "weekly_plans_approved": 5,
                    "instruction_records_validated": 24,
                    "lessons_carried_forward": 2,
                    "documents_requested": 8,
                    "documents_generated": 8,
                    "document_generation_failures": 0,
                }
            ]
        if resource == "school_ai_cost_summary":
            return [
                {
                    "school_id": "school-1",
                    "usage_month": "2026-08-01T00:00:00+00:00",
                    "request_count": 5,
                    "successful_requests": 5,
                    "failed_requests": 0,
                    "input_tokens": 1000,
                    "output_tokens": 400,
                    "cached_tokens": 100,
                    "estimated_cost_usd": 0.25,
                    "accepted_outputs": 4,
                    "discarded_outputs": 1,
                }
            ]
        if resource == "rpc/admin_weekly_submission_status":
            assert payload == {
                "target_week_start": "2026-08-10",
                "target_school_id": None,
            }
            return [
                {
                    "school_id": "school-1",
                    "school_name": "Anniston High School",
                    "teacher_id": "teacher-1",
                    "teacher_name": "Teacher One",
                    "assignment_id": "assignment-1",
                    "course_name": "Pilot English 10",
                    "week_start": "2026-08-10",
                    "revision": 3,
                    "submission_status": "submitted",
                    "submitted_at": "2026-08-08T23:00:00+00:00",
                    "generated_document_count": 1,
                }
            ]
        raise AssertionError(f"Unexpected resource: {resource}")


def test_governed_reporting_views_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeReportingClient()

    def fake_client_factory(
        identity: AuthenticatedTeacher,
        settings: Settings,
    ) -> _FakeReportingClient:
        del identity, settings
        return fake_client

    monkeypatch.setattr(administration_api, "_client", fake_client_factory)

    usage = administration_api.school_usage(_identity("school_admin"), Settings())
    submissions = administration_api.weekly_submissions(
        date(2026, 8, 10),
        _identity("district_admin"),
        Settings(),
        None,
    )
    costs = administration_api.platform_costs(_identity("platform_admin"), Settings())

    assert usage.assignments_configured == 7
    assert usage.data_boundary == "teacher-and-curriculum-only"
    assert len(submissions) == 1
    assert submissions[0].teacher_name == "Teacher One"
    assert submissions[0].submission_status == "submitted"
    assert submissions[0].generated_document_count == 1
    assert len(costs) == 1
    assert str(costs[0].estimated_cost_usd) == "0.25"
