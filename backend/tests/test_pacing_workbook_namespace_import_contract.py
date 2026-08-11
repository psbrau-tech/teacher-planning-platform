from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IMPORTER = ROOT / "frontend" / "src" / "pacingWorkbookImport.ts"


def test_pacing_workbook_import_is_namespace_tolerant() -> None:
    source = IMPORTER.read_text(encoding="utf-8")

    assert 'getElementsByTagNameNS("*", localName)' in source
    assert 'elementsByLocalName(document, "si")' in source
    assert 'elementsByLocalName(item, "t")' in source
    assert 'elementsByLocalName(cell, "v")' in source
    assert 'elementsByLocalName(sheet, "row")' in source
    assert 'elementsByLocalName(row, "c")' in source


def test_pacing_workbook_import_does_not_require_unprefixed_excel_tags() -> None:
    source = IMPORTER.read_text(encoding="utf-8")

    assert 'getElementsByTagName("row")' not in source
    assert 'getElementsByTagName("c")' not in source
    assert 'getElementsByTagName("v")' not in source
    assert 'getElementsByTagName("si")' not in source
    assert 'getElementsByTagName("t")' not in source
