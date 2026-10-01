import type { BenchmarksResponse } from '../api/benchmarks';
import { useBenchmarkView } from '../hooks/useBenchmarkView';
import { orderModels, visibleModels, type Metric } from '../utils/benchmarks';
import BenchmarkControls from './BenchmarkControls';
import BenchmarkMatrix from './BenchmarkMatrix';
import listStyles from './FeedbackList.module.css';
import styles from './BenchmarkResults.module.css';

export default function BenchmarkResults({ data }: { data: BenchmarksResponse }) {
  const [view, updateView] = useBenchmarkView();
  const shown = visibleModels(
    orderModels(data.models, data.summary, view.metric, view.sort),
    view.selected,
  );

  return (
    <>
      {data.error && <PartialResultsBanner message={data.error} />}

      {data.skills.length === 0 ? (
        !data.error && <NoResults lookbackDays={data.lookback_days} />
      ) : (
        <>
          <BenchmarkControls
            models={data.models}
            shown={shown}
            summary={data.summary}
            lookbackDays={data.lookback_days}
            view={view}
            onChange={updateView}
          />
          <BenchmarkMatrix
            skills={data.skills}
            models={shown}
            summary={data.summary}
            testCount={data.test_count}
            lookbackDays={data.lookback_days}
            view={view}
          />
          <ColourLegend metric={view.metric} lookbackDays={data.lookback_days} />
        </>
      )}
    </>
  );
}

function PartialResultsBanner({ message }: { message: string }) {
  return (
    <p className={styles.banner} role="status">
      {message}
    </p>
  );
}

function NoResults({ lookbackDays }: { lookbackDays: number }) {
  return (
    <div className={listStyles.empty}>
      No results in the last {lookbackDays} days.
    </div>
  );
}

function ColourLegend({
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
