from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"


def test_course_setup_ready_requires_saved_standards_mapping() -> None:
    setup = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")
    mapping = (FRONTEND / "StandardsCourseMappingPanel.tsx").read_text(encoding="utf-8")

    assert "const [standardsMapped, setStandardsMapped]" in setup
    assert "const step3Complete = step2Complete && standardsMapped" in setup
    assert "onMappingStatus={setStandardsMapped}" in setup
    assert "onMappingStatus?: (mapped: boolean) => void" in mapping
    assert "onMappingStatus?.(nextMapping.mapped)" in mapping
    assert "onMappingStatus?.(true)" in mapping
    assert "onMappingStatus?.(false)" in mapping


def test_ready_step_exposes_weekly_plan_only_after_all_setup_steps() -> None:
    setup = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")

    ready_block = setup.split('aria-labelledby="course-step-4"', 1)[1]
    assert "step3Complete" in setup
    assert "is ready for weekly planning" in ready_block
    assert "Go to Weekly Plan" in ready_block


def test_course_cards_show_calculated_class_period_minutes() -> None:
    setup = (FRONTEND / "CourseSetupPanel.tsx").read_text(encoding="utf-8")

    assert "function classPeriodMinutes(startTime: string, endTime: string)" in setup
    assert "return end - start" in setup
    assert 'minutes === 1 ? "" : "s"' in setup
    assert "coursePattern ? classScheduleLabel(coursePattern)" in setup
