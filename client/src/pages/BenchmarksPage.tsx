import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { fetchBenchmarks, type BenchmarksResponse } from '../api/benchmarks';
import { useCatalog } from '../context/CatalogContext';
import BenchmarkControls from '../components/BenchmarkControls';
import BenchmarkMatrix from '../components/BenchmarkMatrix';
import FeedbackHeader from '../components/FeedbackHeader';
import listStyles from '../components/FeedbackList.module.css';
import {
  orderModels,
  parseView,
  viewToParams,
  visibleModels,
  type BenchmarkView,
} from '../utils/benchmarks';
import styles from './BenchmarksPage.module.css';

export default function BenchmarksPage() {
  const { benchmarksEnabled, loading: catalogLoading } = useCatalog();
  const { data = null, error, isLoading } = useQuery({
    queryKey: ['benchmarks'],
    queryFn: fetchBenchmarks,
    enabled: !catalogLoading && benchmarksEnabled,
    retry: false,
    staleTime: 60_000,
  });
  const [params, setParams] = useSearchParams();
  const view = parseView(params);

  function updateView(patch: Partial<BenchmarkView>) {
    setParams(
      (current) => viewToParams({ ...parseView(current), ...patch }, current),
      { replace: true },
    );
  }

  return (
    <main className={styles.page}>
      <FeedbackHeader title="Benchmarks" description={describe(data)} />
      <PageBody
        catalogLoading={catalogLoading}
        enabled={benchmarksEnabled}
        loading={isLoading}
        error={error?.message ?? null}
        data={data}
        view={view}
        onViewChange={updateView}
      />
    </main>
  );
}

function describe(data: BenchmarksResponse | null): string {
  if (!data) return 'Latest E2E result per test and model on main.';
  return `${data.project} · latest result per test and model on main, last ${data.lookback_days} days · updated ${new Date(data.generated_at).toLocaleString()}`;
}

function PageBody({
  catalogLoading,
  enabled,
  loading,
  error,
  data,
  view,
  onViewChange,
}: {
  catalogLoading: boolean;
  enabled: boolean;
  loading: boolean;
  error: string | null;
  data: BenchmarksResponse | null;
  view: BenchmarkView;
  onViewChange: (patch: Partial<BenchmarkView>) => void;
}) {
  if (catalogLoading) return <div className={listStyles.loading}>Loading...</div>;
  if (!enabled) {
    return (
      <div className={listStyles.empty}>
        Benchmarks are not enabled on this server.
      </div>
    );
  }
  if (error) {
    return (
      <div className={listStyles.error} role="alert">
        {error}
      </div>
    );
  }
  if (loading || !data) {
    return <div className={listStyles.loading}>Loading benchmarks...</div>;
  }

  return (
    <>
      {data.error ? (
        <p className={styles.banner} role="status">
          {data.error}
        </p>
      ) : null}
      {data.skills.length === 0 ? (
        !data.error && (
          <div className={listStyles.empty}>
            No results in the last {data.lookback_days} days.
          </div>
        )
      ) : (
        <Results data={data} view={view} onViewChange={onViewChange} />
      )}
    </>
  );
}

function Results({
  data,
  view,
  onViewChange,
}: {
  data: BenchmarksResponse;
  view: BenchmarkView;
  onViewChange: (patch: Partial<BenchmarkView>) => void;
}) {
  const shown = visibleModels(
    orderModels(data.models, data.summary, view.metric, view.sort),
    view.selected,
  );
  const history = view.metric === 'history';

  return (
    <>
      <BenchmarkControls
        models={data.models}
        shown={shown}
        summary={data.summary}
        lookbackDays={data.lookback_days}
        view={view}
        onChange={onViewChange}
      />
      <BenchmarkMatrix
        skills={data.skills}
        models={shown}
        summary={data.summary}
        testCount={data.test_count}
        lookbackDays={data.lookback_days}
        view={view}
      />
      <p className={styles.legend}>
        <span className={styles.legendPass}>
          {history ? 'average meets threshold' : 'all tests pass'}
        </span>
        {!history && <span className={styles.legendPartial}>some tests pass</span>}
        <span className={styles.legendFail}>
          {history ? 'average below threshold' : 'no tests pass'}
        </span>
        <span>
          ▲/▼ compare the latest result with the {data.lookback_days}-day
          average. Hover a cell for pipeline, commit and run date. Expand a
          skill for per-test scores and trend.
        </span>
      </p>
    </>
  );
}
