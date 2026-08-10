import { useEffect, useMemo, useState } from "react";

type CatalogCategory = {
  id: string;
  category_key: string;
  display_name: string;
  category_type:
    | "academic_subject"
    | "alternate_achievement_subject"
    | "career_cluster"
    | "general";
  sort_order: number;
};

type CatalogCourse = {
  id: string;
  category_id: string;
  course_key: string;
  display_name: string;
  source_course_code: string | null;
  grade_band: string | null;
};

type MappingState = {
  assignment_id: string;
  mapped: boolean;
  category: CatalogCategory | null;
  course: CatalogCourse | null;
  warning_required_for_change: boolean;
  weekly_plan_count: number;
  validated_week_count: number;
};

type MappingWriteResult = {
  assignment_id: string;
  changed: boolean;
  warning_required: boolean;
  open_selection_count_cleared: number;
  validated_week_count_preserved: number;
  category: CatalogCategory;
  course: CatalogCourse;
};

type StandardsCourseMappingPanelProps = {
  accessToken: string;
  assignmentId: string | null;
  disabled?: boolean;
  onMappingSaved?: (result: MappingWriteResult) => void;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  } catch {
    // Keep the bounded fallback; do not surface raw server/provider content.
  }
  return fallback;
}

export function StandardsCourseMappingPanel({
  accessToken,
  assignmentId,
  disabled = false,
  onMappingSaved,
}: StandardsCourseMappingPanelProps) {
  const [categories, setCategories] = useState<CatalogCategory[]>([]);
  const [courses, setCourses] = useState<CatalogCourse[]>([]);
  const [mapping, setMapping] = useState<MappingState | null>(null);
  const [categoryId, setCategoryId] = useState("");
  const [courseId, setCourseId] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmChecked, setConfirmChecked] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedCategory = useMemo(
    () => categories.find((item) => item.id === categoryId) ?? null,
    [categories, categoryId],
  );
  const selectedCourse = useMemo(
    () => courses.find((item) => item.id === courseId) ?? null,
    [courses, courseId],
  );

  useEffect(() => {
    let active = true;
    setMapping(null);
    setCourses([]);
    setCategoryId("");
    setCourseId("");
    setMessage(null);
    setError(null);
    setConfirming(false);
    setConfirmChecked(false);

    if (!assignmentId) return () => { active = false; };

    const headers = { Authorization: `Bearer ${accessToken}` };
    const load = async () => {
      setLoading(true);
      try {
        const [categoriesResponse, mappingResponse] = await Promise.all([
          fetch("/api/v1/standards/catalog/categories", { headers }),
          fetch(`/api/v1/standards/assignment/${encodeURIComponent(assignmentId)}/mapping`, {
            headers,
          }),
        ]);
        if (!categoriesResponse.ok) {
          throw new Error(await readError(categoriesResponse, "Standards categories could not be loaded."));
        }
        if (!mappingResponse.ok) {
          throw new Error(await readError(mappingResponse, "Standards mapping could not be loaded."));
        }
        const nextCategories = (await categoriesResponse.json()) as CatalogCategory[];
        const nextMapping = (await mappingResponse.json()) as MappingState;
        if (!active) return;
        setCategories(nextCategories);
        setMapping(nextMapping);
        if (nextMapping.mapped && nextMapping.category && nextMapping.course) {
          setCategoryId(nextMapping.category.id);
          const coursesResponse = await fetch(
            `/api/v1/standards/catalog/categories/${encodeURIComponent(nextMapping.category.id)}/courses`,
            { headers },
          );
          if (!coursesResponse.ok) {
            throw new Error(await readError(coursesResponse, "Standards courses could not be loaded."));
          }
          const nextCourses = (await coursesResponse.json()) as CatalogCourse[];
          if (!active) return;
          setCourses(nextCourses);
          setCourseId(nextMapping.course.id);
        }
      } catch (caught) {
        if (!active) return;
        setError(caught instanceof Error ? caught.message : "Standards mapping could not be loaded.");
      } finally {
        if (active) setLoading(false);
      }
    };

    void load();
    return () => { active = false; };
  }, [accessToken, assignmentId]);

  const changeCategory = async (nextCategoryId: string) => {
    setCategoryId(nextCategoryId);
    setCourseId("");
    setCourses([]);
    setMessage(null);
    setError(null);
    setConfirming(false);
    setConfirmChecked(false);
    if (!nextCategoryId) return;
    try {
      const response = await fetch(
        `/api/v1/standards/catalog/categories/${encodeURIComponent(nextCategoryId)}/courses`,
        { headers: { Authorization: `Bearer ${accessToken}` } },
      );
      if (!response.ok) {
        throw new Error(await readError(response, "Standards courses could not be loaded."));
      }
      setCourses((await response.json()) as CatalogCourse[]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Standards courses could not be loaded.");
    }
  };

  const mappingWouldChange = Boolean(
    mapping?.mapped && mapping.course && courseId && mapping.course.id !== courseId,
  );

  const saveMapping = async (confirmed: boolean) => {
    if (!assignmentId || !courseId) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch(
        `/api/v1/standards/assignment/${encodeURIComponent(assignmentId)}/mapping`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            catalog_course_id: courseId,
            confirm_existing_plans: confirmed,
          }),
        },
      );
      if (!response.ok) {
        if (response.status === 409 && mappingWouldChange) {
          setConfirming(true);
          setConfirmChecked(false);
          return;
        }
        throw new Error(await readError(response, "Standards mapping could not be saved."));
      }
      const result = (await response.json()) as MappingWriteResult;
      setMapping((current) => ({
        assignment_id: result.assignment_id,
        mapped: true,
        category: result.category,
        course: result.course,
        warning_required_for_change:
          (current?.weekly_plan_count ?? 0) > 0 || result.warning_required,
        weekly_plan_count: current?.weekly_plan_count ?? 0,
        validated_week_count: result.validated_week_count_preserved,
      }));
      setConfirming(false);
      setConfirmChecked(false);
      setMessage(
        result.open_selection_count_cleared > 0
          ? `Standards mapping updated. ${result.open_selection_count_cleared} unvalidated weekly standards selection${result.open_selection_count_cleared === 1 ? " was" : "s were"} cleared; validated history was preserved.`
          : "Standards mapping saved.",
      );
      onMappingSaved?.(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Standards mapping could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="panel standards-mapping-panel" aria-labelledby="standards-mapping-heading">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Course standards mapping</p>
          <h2 id="standards-mapping-heading">Subject / Career Cluster and Grade / Course</h2>
          <p className="supporting">
            Choose the Alabama standards course that matches this teaching assignment. This mapping
            controls which authoritative standards are available during weekly planning.
          </p>
        </div>
      </div>

      {!assignmentId ? <p>Select a teaching assignment first.</p> : null}
      {loading ? <p>Loading standards catalog…</p> : null}
      {error ? <p className="error-message">{error}</p> : null}
      {message ? <p className="success-message">{message}</p> : null}

      {assignmentId && !loading ? (
        <div className="form-grid">
          <label>
            Subject / Career Cluster
            <select
              value={categoryId}
              disabled={disabled || saving}
              onChange={(event) => void changeCategory(event.target.value)}
            >
              <option value="">Select a subject or career cluster</option>
              {categories.map((category) => (
                <option value={category.id} key={category.id}>{category.display_name}</option>
              ))}
            </select>
          </label>
          <label>
            Grade / Course
            <select
              value={courseId}
              disabled={disabled || saving || !categoryId}
              onChange={(event) => {
                setCourseId(event.target.value);
                setConfirming(false);
                setConfirmChecked(false);
                setMessage(null);
              }}
            >
              <option value="">Select a grade or course</option>
              {courses.map((course) => (
                <option value={course.id} key={course.id}>
                  {course.display_name}
                  {course.source_course_code ? ` · ${course.source_course_code}` : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : null}

      {mapping?.mapped && mapping.category && mapping.course ? (
        <div className="guidance-card">
          <strong>Current mapping</strong>
          <p>{mapping.category.display_name} → {mapping.course.display_name}</p>
          {mapping.validated_week_count > 0 ? (
            <p>{mapping.validated_week_count} validated week{mapping.validated_week_count === 1 ? "" : "s"} will retain their original standards provenance if this mapping is corrected.</p>
          ) : null}
        </div>
      ) : null}

      {confirming && selectedCategory && selectedCourse ? (
        <div className="guidance-card warning-card" role="alert">
          <strong>Change standards mapping?</strong>
          <p>
            This course is currently mapped to {mapping?.category?.display_name} → {mapping?.course?.display_name}.
            You are changing it to {selectedCategory.display_name} → {selectedCourse.display_name}.
          </p>
          <p>
            Previously validated weeks will retain the exact standards and source versions originally
            used. Standards selected for open, unvalidated weeks will be cleared and must be selected
            again. Other planning narrative will remain intact.
          </p>
          <label className="check">
            <input
              type="checkbox"
              checked={confirmChecked}
              onChange={(event) => setConfirmChecked(event.target.checked)}
            />
            I understand that this changes the standards available for current open and future planning.
          </label>
          <div className="button-row">
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setConfirming(false);
                setConfirmChecked(false);
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              className="primary"
              disabled={!confirmChecked || saving}
              onClick={() => void saveMapping(true)}
            >
              {saving ? "Changing mapping…" : "Change standards mapping"}
            </button>
          </div>
        </div>
      ) : (
        <div className="button-row">
          <button
            type="button"
            className="primary"
            disabled={disabled || saving || !courseId || !assignmentId}
            onClick={() => void saveMapping(false)}
          >
            {saving ? "Saving mapping…" : mappingWouldChange ? "Review mapping change" : "Save standards mapping"}
          </button>
        </div>
      )}
    </section>
  );
}
