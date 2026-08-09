import json
from pathlib import Path


def test_frontend_typescript_compiler_is_pinned_for_production_builds() -> None:
    root = Path(__file__).resolve().parents[2]
    package = json.loads((root / "frontend" / "package.json").read_text(encoding="utf-8"))

    # Production image builds must not silently move to a new TypeScript major.
    assert package["dependencies"]["typescript"] == "5.9.2"
