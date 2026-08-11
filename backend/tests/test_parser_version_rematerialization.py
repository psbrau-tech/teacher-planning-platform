from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

from app.standards_maintenance import StandardSourceRecord
from app.standards_parser_rematerialization import stage_parser_rematerialization_if_needed

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "supabase" / "migrations"


class DummyClient:
    pass


def _source() -> StandardSourceRecord:
    return StandardSourceRecord(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        source_key="alabama_academic_english_language_arts",
        landing_url="https://example.test/ela",
        document_url="https://example.test/ela.pdf",
        document_format="pdf",
        resolver_key="test",
        parser_key="alabama_ela_2021",
        source_kind="course_of_study",
        provides_standard_entries=True,
        approved_snapshot_id=UUID("22222222-2222-2222-2222-222222222222"),
    )


def test_parser_upgrade_stages_candidate_when_source_content_is_unchanged(monkeypatch: Any) -> None:
    client = cast(Any, DummyClient())
    source = _source()
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        "app.standards_parser_rematerialization._load_source",
        lambda *_args, **_kwargs: source,
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization._load_approved_materialization",
        lambda *_args, **_kwargs: {
            "normalized_sha256": "n" * 64,
            "parser_version": "gate-e-alabama-ela-2021-v2",
        },
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization.resolve_authoritative_document",
        lambda *_args, **_kwargs: SimpleNamespace(
            document_url="https://example.test/ela.pdf",
            landing_url="https://example.test/ela",
            anchor_text="ELA",
            observed_version="2021",
        ),
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization.fetch_source",
        lambda *_args, **_kwargs: SimpleNamespace(
            source_sha256="s" * 64,
            resolved_url="https://example.test/ela.pdf",
        ),
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization.extract_document",
        lambda *_args, **_kwargs: SimpleNamespace(normalized_sha256="n" * 64),
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization.parse_document",
        lambda *_args, **_kwargs: SimpleNamespace(
            parser_version="gate-e-alabama-ela-2021-v3",
            courses=(),
        ),
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization._update_resolved_document_url",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization._stage_parser_version_candidate",
        lambda *_args, **_kwargs: UUID("33333333-3333-3333-3333-333333333333"),
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization._persist_parsed_standards",
        lambda *_args, **_kwargs: calls.__setitem__("persisted", True),
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization._mark_source_check_as_parser_change",
        lambda *_args, **_kwargs: calls.__setitem__("check_updated", True),
    )

    result = stage_parser_rematerialization_if_needed(
        client,
        source.source_key,
        check_date=date(2026, 8, 10),
    )

    assert result is not None
    assert result.status == "changed"
    assert result.candidate_snapshot_id == UUID("33333333-3333-3333-3333-333333333333")
    assert "v2 to gate-e-alabama-ela-2021-v3" in result.detail
    assert calls == {"persisted": True, "check_updated": True}


def test_same_parser_version_does_not_stage_rematerialization(monkeypatch: Any) -> None:
    client = cast(Any, DummyClient())
    source = _source()

    monkeypatch.setattr(
        "app.standards_parser_rematerialization._load_source",
        lambda *_args, **_kwargs: source,
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization._load_approved_materialization",
        lambda *_args, **_kwargs: {
            "normalized_sha256": "n" * 64,
            "parser_version": "gate-e-alabama-ela-2021-v3",
        },
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization.resolve_authoritative_document",
        lambda *_args, **_kwargs: SimpleNamespace(
            document_url="https://example.test/ela.pdf",
            landing_url="https://example.test/ela",
            anchor_text="ELA",
            observed_version="2021",
        ),
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization.fetch_source",
        lambda *_args, **_kwargs: SimpleNamespace(
            source_sha256="s" * 64,
            resolved_url="https://example.test/ela.pdf",
        ),
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization.extract_document",
        lambda *_args, **_kwargs: SimpleNamespace(normalized_sha256="n" * 64),
    )
    monkeypatch.setattr(
        "app.standards_parser_rematerialization.parse_document",
        lambda *_args, **_kwargs: SimpleNamespace(
            parser_version="gate-e-alabama-ela-2021-v3",
            courses=(),
        ),
    )

    assert (
        stage_parser_rematerialization_if_needed(
            client,
            source.source_key,
            check_date=date(2026, 8, 10),
        )
        is None
    )


def test_snapshot_uniqueness_is_parser_versioned() -> None:
    migration = (
        MIGRATIONS / "20260810154500_parser_versioned_standard_snapshots.sql"
    ).read_text(encoding="utf-8")
    assert "drop constraint if exists standard_snapshots_source_id_source_sha256_key" in migration
    assert "standard_snapshots_source_hash_parser_version_key" in migration
    assert "coalesce(parser_version, '')" in migration
