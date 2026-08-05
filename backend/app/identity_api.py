from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .auth import AuthenticatedTeacher, require_teacher

router = APIRouter(prefix="/api/v1/session", tags=["authentication"])


class SessionIdentityRead(BaseModel):
    id: str
    email: str
    display_name: str
    school_id: str
    roles: list[str]
    data_boundary: str


@router.get("", response_model=SessionIdentityRead)
def current_session(
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
) -> SessionIdentityRead:
    if identity.school_id is None:
        raise RuntimeError("Governed identity is missing a school")
    return SessionIdentityRead(
        id=identity.subject,
        email=identity.email,
        display_name=identity.display_name,
        school_id=identity.school_id,
        roles=sorted(identity.roles),
        data_boundary="teacher-and-curriculum-only",
    )
