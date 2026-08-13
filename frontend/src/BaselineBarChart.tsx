import "./BaselineBarChart.css";

type BaselineChartResponse = {
  plan_usefulness_before: number;
  submission_burden_before: number;
  reflection_review_frequency_before: string;
  plc_use_frequency_before: string;
};

type Props = {
  responses: BaselineChartResponse[];
};

type Question = {
  key: string;
  label: string;
  scores: number[];
};

const FREQUENCY_SCORE: Record<string, number> = {
  never: 1,
  rarely: 2,
  sometimes: 3,
  often: 4,
  very_often: 5,
};

function countScores(values: number[]): number[] {
  return [1, 2, 3, 4, 5].map((score) => values.filter((value) => value === score).length);
}

export function BaselineBarChart({ responses }: Props) {
  const questions: Question[] = [
    {
      key: "usefulness",
      label: "Plan usefulness",
      scores: countScores(responses.map((response) => response.plan_usefulness_before)),
    },
    {
      key: "burden",
      label: "Submission burden",
      scores: countScores(responses.map((response) => response.submission_burden_before)),
    },
    {
      key: "reflection",
      label: "Revisited reflections",
      scores: countScores(responses.map((response) => FREQUENCY_SCORE[response.reflection_review_frequency_before] ?? 0)),
    },
    {
      key: "plc",
      label: "Used in PLC/faculty discussion",
      scores: countScores(responses.map((response) => FREQUENCY_SCORE[response.plc_use_frequency_before] ?? 0)),
    },
  ];
  const maxCount = Math.max(1, ...questions.flatMap((question) => question.scores));

  return (
    <section className="baseline-bar-chart" aria-label="Pre-TPP baseline score distribution">
      <div className="baseline-chart-heading">
        <div>
          <h4>Baseline response distribution</h4>
          <p>Number of teacher responses at each 1–5 score for each scaled baseline question.</p>
        </div>
      </div>
      <div className="baseline-grouped-chart" role="img" aria-label="Grouped vertical bar chart showing response counts for scores one through five across plan usefulness, submission burden, revisiting reflections, and use in PLC or faculty discussion">
        {questions.map((question) => (
          <div className="baseline-question-group" key={question.key}>
            <strong>{question.label}</strong>
            <div className="baseline-bars">
              {question.scores.map((count, index) => (
                <div className="baseline-bar-column" key={`${question.key}-${index + 1}`}>
                  <span className="baseline-bar-count">{count}</span>
                  <div className="baseline-bar-track">
                    <div
                      className="baseline-score-bar"
                      style={{ height: count === 0 ? "0" : `${Math.max(10, (count / maxCount) * 100)}%` }}
                      title={`${question.label}: score ${index + 1} — ${count} response${count === 1 ? "" : "s"}`}
                    />
                  </div>
                  <span className="baseline-score-label">Score {index + 1}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="baseline-chart-note">For frequency questions, 1 = Never, 2 = Rarely, 3 = Sometimes, 4 = Often, and 5 = Very often. Usefulness and burden retain the original 1–5 survey scales.</p>
    </section>
  );
}
