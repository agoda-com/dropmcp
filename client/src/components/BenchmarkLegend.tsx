import type { Metric } from '../utils/benchmarks';
import styles from './BenchmarkLegend.module.css';

export default function BenchmarkLegend({
  metric,
  lookbackDays,
}: {
  metric: Metric;
  lookbackDays: number;
}) {
  const history = metric === 'history';

  return (
    <p className={styles.legend}>
      <span className={styles.legendPass}>
        {history ? 'average meets threshold' : 'all tests pass'}
      </span>
      {!history && <span className={styles.legendPartial}>some tests pass</span>}
      <span className={styles.legendFail}>
        {history ? 'average below threshold' : 'no tests pass'}
      </span>
      <span>
        ▲/▼ compare the latest result with the {lookbackDays}-day average. Hover
        a cell for pipeline, commit and run date. Expand a skill for per-test
        scores and trend.
      </span>
    </p>
  );
}
