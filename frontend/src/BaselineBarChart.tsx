type Props = {
  averageUsefulness: number;
  averageBurden: number;
  rarelyReviewReflection: number;
  rarelyUseInPlc: number;
  responseCount: number;
};

export function BaselineBarChart(props: Props) {
  const count = Math.max(1, props.responseCount);
  return (
    <section className="baseline-bar-chart" aria-label="Pre-TPP baseline bar chart">
      <h4>Baseline at a glance</h4>
      <div><span>Plan usefulness</span><meter min={0} max={5} value={props.averageUsefulness} /><strong>{props.averageUsefulness.toFixed(1)}/5</strong></div>
      <div><span>Submission burden</span><meter min={0} max={5} value={props.averageBurden} /><strong>{props.averageBurden.toFixed(1)}/5</strong></div>
      <div><span>Never / rarely revisited reflections</span><meter min={0} max={count} value={props.rarelyReviewReflection} /><strong>{props.rarelyReviewReflection}/{props.responseCount}</strong></div>
      <div><span>Never / rarely used in PLC/faculty discussion</span><meter min={0} max={count} value={props.rarelyUseInPlc} /><strong>{props.rarelyUseInPlc}/{props.responseCount}</strong></div>
    </section>
  );
}
