from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_required_project_documents_exist():
    required = [
        "README.md",
        "docs/project-card.md",
        "docs/decision-log.md",
        "docs/working-agreements.md",
        "docs/release-plan.md",
    ]
    missing = [path for path in required if not (ROOT / path).exists()]
    assert not missing, f"Missing required files: {missing}"


def test_working_agreements_include_delivery_rules():
    text = (ROOT / "docs/working-agreements.md").read_text(encoding="utf-8")
    for term in ("Definition of Ready", "Definition of Done", "WIP"):
        assert term in text, f"working-agreements.md must contain {term}"


def test_release_plan_contains_rollback_and_checklist():
    text = (ROOT / "docs/release-plan.md").read_text(encoding="utf-8").lower()
    for term in ("окно релиза", "чек-лист", "откат", "ответствен"):
        assert term in text, f"release-plan.md must contain {term}"
