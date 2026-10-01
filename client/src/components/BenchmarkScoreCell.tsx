import type { BenchmarkAggregate, BenchmarkStatus } from '../api/benchmarks';
import { formatDelta, formatNumber } from '../utils/benchmarks';
import styles from './BenchmarkMatrix.module.css';

export default function BenchmarkScoreCell({
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
