import styles from './BenchmarkMatrix.module.css';

export default function BenchmarkEmptyCell() {
  return <td className={styles.missing}>—</td>;
}
