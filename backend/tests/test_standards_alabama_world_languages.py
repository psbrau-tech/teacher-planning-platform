from hashlib import sha256

import pytest

from app.standards_alabama_world_languages import parse_alabama_world_languages_2017
from app.standards_ingest import ExtractedDocument, StandardsIngestError

PROFICIENCIES = (
    "Novice Low Proficiency Range",
    "Novice Mid Proficiency Range",
    "Novice High Proficiency Range",
    "Intermediate Low Proficiency Range",
    "Intermediate Mid Proficiency Range",
    "Intermediate High Proficiency Range",
)
WORLD_LEVELS = ("Level I", "Level II", "Level III", "Level IV", "Level V")
FOUR_LEVELS = WORLD_LEVELS[:4]


def _section(program: str, grades: str | None, heading: str) -> list[str]:
    lines = [program]
    if grades is not None:
        lines.append(grades)
    lines.extend([heading, "Students can:", "Communication", "Interpersonal Mode"])
    for number in range(1, 9):
        lines.append(f"{number}. Required language standard {number} for {heading}.")
        if number == 1:
            lines.extend(
                [
                    "a. Required supporting language skill.",
                    "Examples: Supplemental example must not become authoritative wording.",
                    "Example continuation must also be excluded.",
                    "b. Required supporting cultural skill.",
                ]
            )
        if number == 4:
            lines.append("Cultures")
    return lines


def _document(
    *,
    omit_heading: str | None = None,
    include_appendix: bool = True,
) -> ExtractedDocument:
    lines: list[str] = []
    for heading in PROFICIENCIES:
        if heading != omit_heading:
            lines.extend(_section("World Languages", "Grades K-8", heading))
    for heading in WORLD_LEVELS:
        if heading != omit_heading:
            lines.extend(_section("World Languages", "Grades 7 – 12", heading))
    for heading in FOUR_LEVELS:
        if f"Latin {heading}" != omit_heading:
            lines.extend(_section("LATIN", None, heading))
    for heading in PROFICIENCIES:
        if f"ASL {heading}" != omit_heading:
            lines.extend(_section("American Sign Language", "Grades K–8", heading))
    for heading in FOUR_LEVELS:
        if f"ASL {heading}" != omit_heading:
            lines.extend(_section("American Sign Language", "Grades 7 – 12", heading))
    if include_appendix:
        lines.extend(
            [
                "Appendix A",
                "Latin Grammar Addendum",
                "1. Appendix numbered material must not become an ASL standard.",
                "2. Additional appendix numbering must remain outside governed course text.",
            ]
        )
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_world_languages_parser_returns_all_25_current_course_views() -> None:
    parsed = parse_alabama_world_languages_2017(_document())

    assert len(parsed.courses) == 25
    assert parsed.courses[0].course_key == "world_languages_k8_novice_low"
    assert parsed.courses[5].course_key == "world_languages_k8_intermediate_high"
    assert parsed.courses[6].course_key == "world_languages_level_i"
    assert parsed.courses[10].course_key == "world_languages_level_v"
    assert parsed.courses[11].course_key == "latin_level_i"
    assert parsed.courses[14].course_key == "latin_level_iv"
    assert parsed.courses[15].course_key == "asl_k8_novice_low"
    assert parsed.courses[-1].course_key == "asl_level_iv"


def test_world_languages_parser_preserves_goal_strands_children_and_excludes_examples() -> None:
    parsed = parse_alabama_world_languages_2017(_document())
    level_one = next(
        course for course in parsed.courses if course.course_key == "world_languages_level_i"
    )
    by_code = {standard.code: standard for standard in level_one.standards}

    assert by_code["1"].strand == "Communication"
    assert by_code["1a"].parent_code == "1"
    assert by_code["1a"].text == "Required supporting language skill."
    assert "Supplemental example" not in by_code["1a"].text
    assert by_code["1b"].parent_code == "1"
    assert by_code["4"].strand == "Communication"
    assert by_code["5"].strand == "Cultures"


def test_world_languages_parser_stops_final_asl_section_before_appendix() -> None:
    parsed = parse_alabama_world_languages_2017(_document())
    asl_four = next(course for course in parsed.courses if course.course_key == "asl_level_iv")

    assert [
        standard.code for standard in asl_four.standards if standard.parent_code is None
    ] == [str(number) for number in range(1, 9)]
    assert all("Appendix numbered material" not in standard.text for standard in asl_four.standards)


def test_world_languages_parser_fails_closed_when_appendix_boundary_is_missing() -> None:
    with pytest.raises(StandardsIngestError, match="Appendix A boundary"):
        parse_alabama_world_languages_2017(_document(include_appendix=False))


def test_world_languages_parser_fails_closed_when_required_section_is_missing() -> None:
    with pytest.raises(StandardsIngestError, match="Latin Level III"):
        parse_alabama_world_languages_2017(_document(omit_heading="Latin Level III"))


def test_world_languages_parser_fails_closed_on_nonconsecutive_main_standards() -> None:
    document = _document()
    lines = list(document.lines)
    marker = lines.index("World Languages")
    first_section = lines.index("Novice Low Proficiency Range", marker)
    standard_three = lines.index(
        "3. Required language standard 3 for Novice Low Proficiency Range.",
        first_section,
    )
    del lines[standard_three]
    normalized = "\n".join(lines)

    with pytest.raises(StandardsIngestError, match="invalid main-standard sequence"):
        parse_alabama_world_languages_2017(
            ExtractedDocument(
                lines=tuple(lines),
                normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
            )
        )
