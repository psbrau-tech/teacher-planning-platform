from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"


def test_completed_weekly_steps_remain_reopenable_without_erasing_work() -> None:
    shell = (FRONTEND / "TeacherPlanningShell.tsx").read_text(encoding="utf-8")

    assert "Edit standards" in shell
    assert "Reopen planning assistance" in shell
    assert "Edit plan" in shell
    assert "View PDF" in shell
    assert "Download PDF" in shell
    assert "Print" in shell
    assert "teacher-authored planning text is preserved" in shell.lower()


def test_completed_course_setup_steps_remain_editable() -> None:
    setup = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")

    assert "Edit Class & Schedule" in setup
    assert "Edit current curriculum" in setup
    assert "Download Excel" in setup
    assert "Create new version / copy" in setup
    assert "Change / reuse curriculum" in setup
    assert "Edit standards mapping" in setup
    assert "Go to Weekly Plan" in setup


def test_completed_packet_controls_persist_after_first_review() -> None:
    shell = (FRONTEND / "TeacherPlanningShell.tsx").read_text(encoding="utf-8")

    assert "Step 3 complete · Completed Weekly Packet reviewed" in shell
    assert "View packet" in shell
    assert "exportCompletedPacket(\"download\")" in shell
    assert "exportCompletedPacket(\"print\")" in shell
