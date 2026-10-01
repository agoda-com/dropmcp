import type { BenchmarkSummary } from '../api/benchmarks';
import {
  deltaAgainstHistory,
  historyStatus,
  historyTitle,
  overallSubLine,
  type BenchmarkView,
} from '../utils/benchmarks';
import BenchmarkScoreCell from './BenchmarkScoreCell';

export default function BenchmarkOverallCell({
  summary,
  testCount,
  view,
  lookbackDays,
  className,
}: {
  summary: BenchmarkSummary;
  testCount: number;
  className?: string;
  view: BenchmarkView;
  lookbackDays: number;
}) {
  const source = view.metric === 'history' ? summary.history : summary;

  return (
    <BenchmarkScoreCell
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
