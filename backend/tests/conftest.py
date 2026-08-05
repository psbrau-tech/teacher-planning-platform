from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Header, HTTPException

from app.auth import AuthenticatedTeacher, require_teacher
from app.main import app


@pytest.fixture(autouse=True)
def authenticated_teacher_override() -> Iterator[None]:
    """Preserve deterministic API tests without bypassing production auth code."""

    def test_teacher(
        teacher_id: Annotated[str | None, Header(alias="X-TPP-Teacher-ID")] = None,
    ) -> AuthenticatedTeacher:
        if teacher_id is None or not teacher_id.strip():
            raise HTTPException(status_code=401, detail="Teacher identity is required")
        subject = teacher_id.strip()
        return AuthenticatedTeacher(
            subject=subject,
            email=f"{subject}@example.test",
            display_name=subject,
        )

    app.dependency_overrides[require_teacher] = test_teacher
    yield
    app.dependency_overrides.pop(require_teacher, None)
