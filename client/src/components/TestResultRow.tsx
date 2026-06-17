import type { SkillTelemetryResult } from '../api/catalog';
import styles from './TelemetryPanel.module.css';

function StatusDot({ passed }: { passed: boolean }) {
  return (
    <span className={passed ? styles.passDot : styles.failDot} />
  );
}

export default function TestResultRow({ result }: { result: SkillTelemetryResult }) {
  return (
    <>
      <tr className={`${styles.row} ${result.passed ? styles.passed : styles.failed}`}>
        <td><StatusDot passed={result.passed} /></td>
        <td className={styles.model}>{result.worker_model}</td>
        <td>
          <span className={result.passed ? styles.scorePass : styles.scoreFail}>
            {result.display_score}
          </span>
          <span className={styles.threshold}>{result.display_threshold}</span>
        </td>
        <td>{result.display_duration}</td>
        <td className={styles.date}>{result.display_date}</td>
      </tr>
      {result.reasoning && (
        <tr className={styles.reasoningRow}>
          <td></td>
          <td colSpan={4} className={styles.reasoningCell}>
            {result.reasoning}
          </td>
        </tr>
      )}
    </>
  );
}
