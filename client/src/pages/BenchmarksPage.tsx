import type { BenchmarksResponse } from '../api/benchmarks';
import BenchmarkResults from '../components/benchmarks/BenchmarkResults';
import FeedbackHeader from '../components/FeedbackHeader';
import listStyles from '../components/feedback/FeedbackList.module.css';
import { useBenchmarks } from '../hooks/useBenchmarks';
import styles from './BenchmarksPage.module.css';

export default function BenchmarksPage() {
  const benchmarks = useBenchmarks();

  return (
    <main className={styles.page}>
      <FeedbackHeader title="Benchmarks" description={describe(benchmarks.data)} />
      <BenchmarksBody {...benchmarks} />
    </main>
  );
}

function describe(data: BenchmarksResponse | null): string {
  if (!data) return 'Latest E2E result per test and model on main.';
  return `${data.project} · latest result per test and model on main, last ${data.lookback_days} days · updated ${new Date(data.generated_at).toLocaleString()}`;
}

function BenchmarksBody({
  catalogLoading,
  enabled,
  loading,
  error,
  data,
}: ReturnType<typeof useBenchmarks>) {
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

  return <BenchmarkResults data={data} />;
}
