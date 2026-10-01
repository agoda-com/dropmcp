import type { BenchmarkCell } from '../../../api/benchmarks';
import {
  deltaAgainstHistory,
  historyStatus,
  historyTitle,
  runTitle,
  skillSubLine,
  type BenchmarkView,
} from '../../../utils/benchmarks';
import BenchmarkEmptyCell from './BenchmarkEmptyCell';
import BenchmarkScoreCell from './BenchmarkScoreCell';

export default function BenchmarkSkillCell({
  cell,
  testCount,
  view,
  lookbackDays,
}: {
  cell: BenchmarkCell | undefined;
  testCount: number;
  view: BenchmarkView;
  lookbackDays: number;
}) {
  if (!cell) return <BenchmarkEmptyCell />;
  const source = view.metric === 'history' ? cell.history : cell;

  return (
    <BenchmarkScoreCell
      source={source}
      delta={view.metric === 'latest' ? deltaAgainstHistory(cell) : null}
      sub={skillSubLine(source, view.metric, testCount)}
      compact={view.compact}
      title={`${runTitle(cell)}\n${historyTitle(cell.history, lookbackDays)}`}
      status={view.metric === 'history' ? historyStatus(source) : source.status}
    />
  );
}
