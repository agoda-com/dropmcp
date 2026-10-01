import type { BenchmarkSummary } from '../api/benchmarks';
import type { BenchmarkView } from '../utils/benchmarks';
import BenchmarkEmptyCell from './BenchmarkEmptyCell';
import BenchmarkOverallCell from './BenchmarkOverallCell';
import styles from './BenchmarkMatrix.module.css';

interface Props {
  models: string[];
  summary: Record<string, BenchmarkSummary>;
  testCount: number;
  lookbackDays: number;
  view: BenchmarkView;
}

export default function BenchmarkOverallRow({
  models,
  summary,
  testCount,
  lookbackDays,
  view,
}: Props) {
  return (
    <tr className={styles.overallRow}>
      <th scope="row" className={styles.nameCol}>
        Overall
        <span className={styles.count}>{testCount} tests</span>
      </th>
      <BenchmarkEmptyCell />
      {models.map((model) => (
        <BenchmarkOverallCell
          key={model}
          summary={summary[model]}
          testCount={testCount}
          view={view}
          lookbackDays={lookbackDays}
        />
      ))}
    </tr>
  );
}
