import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_required_project_documents_exist():
    required = [
        "README.md",
        "docs/project-card.md",
        "docs/decision-log.md",
        "docs/working-agreements.md",
        "docs/release-plan.md",
        "docs/dora-manual-releases.json",
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


def test_manual_dora_release_is_reproducible():
    path = ROOT / "docs/dora-manual-releases.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    releases = data.get("manual_deployments", [])
    assert releases, "At least one manual release must be recorded"
    release = releases[0]
    assert release["platform"] == "Tilda"
    assert release["status"] == "success"
    assert release["started_at"] and release["deployed_at"]
