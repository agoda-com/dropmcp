import type { BenchmarksResponse } from '../../api/benchmarks';
import { useBenchmarkView } from '../../hooks/useBenchmarkView';
import { orderModels, visibleModels } from '../../utils/benchmarks';
import BenchmarkControls from './controls/BenchmarkControls';
import BenchmarkLegend from './BenchmarkLegend';
import BenchmarkMatrix from './matrix/BenchmarkMatrix';
import listStyles from '../feedback/FeedbackList.module.css';
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
          <BenchmarkLegend metric={view.metric} lookbackDays={data.lookback_days} />
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
