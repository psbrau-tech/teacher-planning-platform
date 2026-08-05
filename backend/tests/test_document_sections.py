from app.document_sections import (
    HqiDocument,
    continuation_requirements,
    document_for_field,
)


def test_each_source_page_is_a_separate_document() -> None:
    assert document_for_field("standards") == HqiDocument.INSTRUCTIONAL_FRAMEWORK
    assert document_for_field("clt_mon") == HqiDocument.WEEK_AT_A_GLANCE
    assert document_for_field("reflect_12") == HqiDocument.WEEKLY_REFLECTION


def test_long_content_requires_continuation_instead_of_shrinking() -> None:
    requirements = continuation_requirements(
        {
            "standards": "x" * 500,
            "clt_mon": "y" * 300,
            "reflect_1": "z" * 500,
        }
    )

    assert {requirement.document for requirement in requirements} == {
        HqiDocument.INSTRUCTIONAL_FRAMEWORK,
        HqiDocument.WEEK_AT_A_GLANCE,
        HqiDocument.WEEKLY_REFLECTION,
    }
    assert all(
        requirement.character_count > requirement.first_page_capacity
        for requirement in requirements
    )


def test_short_content_does_not_require_continuation() -> None:
    assert continuation_requirements({"teacher": "Peter", "course": "LET 1"}) == ()
