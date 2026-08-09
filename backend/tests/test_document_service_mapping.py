import json

from app.document_service import normalize_planning_payload


def test_integrated_weekly_plan_maps_only_defensible_pdf_equivalents() -> None:
    payload = {
        "teacher": "Synthetic Teacher",
        "course": "Army JROTC LET 1",
        "grade": "9-12",
        "week_of": "2026-08-17",
        "unit_topic": "Drill and Ceremony",
        "standards": "U1C3L2 — Stationary Movements and Marching Techniques",
        "literacy_standards": "ELA recurring standard text",
        "act_preparation": "ACT reference application",
        "learning_targets": "Demonstrate positions of attention and rest.",
        "know": "Commands and terminology",
        "understand": "Precision supports unit performance",
        "do": "Demonstrate stationary movements",
        "activities": "Model, rehearse, and peer-coach stationary movements.",
        "assessments": "Performance check and exit ticket.",
        "resources": "Cadet reference and drill area.",
        "monday": "Introduce attention and positions of rest.",
        "tuesday": "Practice stationary movements.",
        "wednesday": "",
        "thursday": "",
        "friday": "",
        "reflection": json.dumps(
            {f"reflect_{index}": f"Class-level response {index}" for index in range(1, 13)}
        ),
    }

    normalized = normalize_planning_payload(payload)

    assert normalized["teacher"] == "Synthetic Teacher"
    assert normalized["standards"].startswith("U1C3L2")
    assert normalized["know"] == payload["know"]
    assert normalized["understand"] == payload["understand"]
    assert normalized["do"] == payload["do"]
    assert normalized["resources"] == payload["resources"]
    assert normalized["clt_mon"] == payload["learning_targets"]
    assert normalized["rrt_mon"] == payload["monday"]
    assert normalized["clt_tue"] == payload["learning_targets"]
    assert normalized["rrt_tue"] == payload["tuesday"]
    assert "clt_wed" not in normalized
    assert "rrt_wed" not in normalized
    assert "plds" not in normalized
    assert "formative" not in normalized
    assert "summative" not in normalized
    assert "performance_task" not in normalized
    assert "cfu_mon" not in normalized
    assert "esl_mon" not in normalized
    assert normalized["reflect_1"] == "Class-level response 1"
    assert normalized["reflect_12"] == "Class-level response 12"


def test_exact_pdf_fields_are_preserved_when_teacher_supplies_them() -> None:
    normalized = normalize_planning_payload(
        {
            "learning_targets": "Integrated learning target",
            "monday": "Integrated Monday narrative",
            "plds": "Teacher-authored proficiency descriptor",
            "activities": "Integrated activity",
            "performance_task": "Teacher-authored performance task",
            "clt_mon": "Teacher-authored Monday learning target",
            "rrt_mon": "Teacher-authored Monday task",
            "cfu_mon": "Teacher-authored Monday check for understanding",
        }
    )

    assert normalized["plds"] == "Teacher-authored proficiency descriptor"
    assert normalized["performance_task"] == "Teacher-authored performance task"
    assert normalized["clt_mon"] == "Teacher-authored Monday learning target"
    assert normalized["rrt_mon"] == "Teacher-authored Monday task"
    assert normalized["cfu_mon"] == "Teacher-authored Monday check for understanding"
