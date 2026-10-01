import type { BenchmarkAggregate, BenchmarkRun } from '../../../api/benchmarks';
import {
  formatNumber,
  historyStatus,
  historyTitle,
  runTitle,
  type BenchmarkView,
} from '../../../utils/benchmarks';
import BenchmarkEmptyCell from './BenchmarkEmptyCell';
import Sparkline from './Sparkline';
import styles from './BenchmarkMatrix.module.css';

export default function BenchmarkTestCell({
  run,
  view,
  lookbackDays,
}: {
  run: BenchmarkRun | undefined;
  view: BenchmarkView;
  lookbackDays: number;
}) {
  if (!run) return <BenchmarkEmptyCell />;
  const title = `${runTitle(run)}\n${historyTitle(run.history, lookbackDays)}`;

  return view.metric === 'history' ? (
    <TestAverageCell history={run.history} compact={view.compact} title={title} />
  ) : (
    <TestLatestCell run={run} compact={view.compact} title={title} />
  );
}

function TestAverageCell({
  history,
  compact,
  title,
}: {
  history: BenchmarkAggregate;
  compact: boolean;
  title: string;
}) {
  return (
    <td className={styles[historyStatus(history)]} title={title}>
      {compact
        ? formatNumber(history.average_score)
        : `avg ${formatNumber(history.average_score)} · ${history.passed}/${history.total} runs`}
    </td>
  );
}

function TestLatestCell({
  run,
  compact,
  title,
}: {
  run: BenchmarkRun;
  compact: boolean;
  title: string;
}) {
  const mark = run.passed ? '✓' : '✗';

  return (
    <td className={run.passed ? styles.pass : styles.fail} title={title}>
      {compact
        ? `${formatNumber(run.score)} ${mark}`
        : `${formatNumber(run.score)} / ${formatNumber(run.threshold)} ${mark}`}
      {!compact && run.series.length >= 2 && <Sparkline values={run.series} />}
    </td>
  );
}
