import type {
  BenchmarkAggregate,
  BenchmarkCell,
  BenchmarkRun,
  BenchmarkStatus,
  BenchmarkSummary,
} from '../api/benchmarks';
import {
  deltaAgainstHistory,
  formatDelta,
  formatNumber,
  historyStatus,
  historyTitle,
  overallSubLine,
  runTitle,
  skillSubLine,
  type BenchmarkView,
} from '../utils/benchmarks';
import Sparkline from './Sparkline';
import styles from './BenchmarkMatrix.module.css';

interface CellProps {
  view: BenchmarkView;
  lookbackDays: number;
}

export function EmptyCell() {
  return <td className={styles.missing}>—</td>;
}

export function OverallCell({
  summary,
  testCount,
  view,
  lookbackDays,
  className,
}: CellProps & {
  summary: BenchmarkSummary;
  testCount: number;
  className?: string;
}) {
  const source = view.metric === 'history' ? summary.history : summary;

  return (
    <ScoreCell
      source={source}
      delta={view.metric === 'latest' ? deltaAgainstHistory(summary) : null}
      sub={overallSubLine(source, view.metric, testCount)}
      compact={view.compact}
      title={historyTitle(summary.history, lookbackDays)}
      status={view.metric === 'history' ? historyStatus(source) : source.status}
      className={className}
    />
  );
}

export function SkillCell({
  cell,
  testCount,
  view,
  lookbackDays,
}: CellProps & {
  cell: BenchmarkCell | undefined;
  testCount: number;
}) {
  if (!cell) return <EmptyCell />;
  const source = view.metric === 'history' ? cell.history : cell;

  return (
    <ScoreCell
      source={source}
      delta={view.metric === 'latest' ? deltaAgainstHistory(cell) : null}
      sub={skillSubLine(source, view.metric, testCount)}
      compact={view.compact}
      title={`${runTitle(cell)}\n${historyTitle(cell.history, lookbackDays)}`}
      status={view.metric === 'history' ? historyStatus(source) : source.status}
    />
  );
}

export function TestCell({
  run,
  view,
  lookbackDays,
}: CellProps & { run: BenchmarkRun | undefined }) {
  if (!run) return <EmptyCell />;
  const title = `${runTitle(run)}\n${historyTitle(run.history, lookbackDays)}`;

  return view.metric === 'history' ? (
    <TestAverageCell history={run.history} compact={view.compact} title={title} />
  ) : (
    <TestLatestCell run={run} compact={view.compact} title={title} />
  );
}

function ScoreCell({
  source,
  delta,
  sub,
  compact,
  title,
  status,
  className = '',
}: {
  source: BenchmarkAggregate;
  delta: number | null;
  sub: string;
  compact: boolean;
  title: string;
  status: BenchmarkStatus;
  className?: string;
}) {
  return (
    <td className={`${styles[status]} ${className}`} title={title}>
      <span className={styles.score}>
        {formatNumber(source.average_score)}
        {delta !== null && !compact && <ScoreDelta delta={delta} />}
      </span>
      {!compact && <span className={styles.sub}>{sub}</span>}
    </td>
  );
}

function ScoreDelta({ delta }: { delta: number }) {
  return <span className={delta > 0 ? styles.up : styles.down}>{formatDelta(delta)}</span>;
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
