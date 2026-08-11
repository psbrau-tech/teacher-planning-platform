from __future__ import annotations

import argparse
import json
import sys

from app.standards_course_catalog import parse_course_catalog_document
from app.standards_ingest import StandardsIngestError, extract_document, fetch_source
from app.standards_parser_dispatch import parse_governed_standards_document


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch and inspect one authoritative standards document without writing "
            "to the database."
        )
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--format", required=True, choices=("pdf", "docx"))
    parser.add_argument("--parser-key", required=True)
    parser.add_argument(
        "--course-catalog",
        action="store_true",
        help="Interpret the source as a course-listing catalog rather than standards text.",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    fetched = fetch_source(args.url, args.format)
    extracted = extract_document(fetched)

    if args.course_catalog:
        parsed = parse_course_catalog_document(args.parser_key, extracted)
        payload = {
            "source_sha256": fetched.source_sha256,
            "normalized_sha256": extracted.normalized_sha256,
            "parser_key": parsed.parser_key,
            "parser_version": parsed.parser_version,
            "course_count": len(parsed.courses),
            "courses": [
                {
                    "course_key": course.course_key,
                    "display_name": course.display_name,
                    "source_course_code": course.source_course_code,
                    "grade_band": course.grade_band,
                }
                for course in parsed.courses
            ],
            "database_writes": 0,
        }
    else:
        parsed = parse_governed_standards_document(args.parser_key, extracted)
        payload = {
            "source_sha256": fetched.source_sha256,
            "normalized_sha256": extracted.normalized_sha256,
            "parser_key": parsed.parser_key,
            "parser_version": parsed.parser_version,
            "course_count": len(parsed.courses),
            "standard_count": sum(len(course.standards) for course in parsed.courses),
            "courses": [
                {
                    "course_key": course.course_key,
                    "display_name": course.display_name,
                    "grade_band": course.grade_band,
                    "standard_count": len(course.standards),
                }
                for course in parsed.courses
            ],
            "database_writes": 0,
        }

    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except StandardsIngestError as error:
        print(
            json.dumps(
                {
                    "status": "parser_error",
                    "detail": str(error),
                    "database_writes": 0,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2) from error
