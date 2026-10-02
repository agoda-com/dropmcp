import type { MemoryReport } from '../../api/memory';
import styles from './memory.module.css';

export default function MemoryReportRow({ report }: { report: MemoryReport }) {
  return (
    <article className={styles.report} aria-label={report.problem_label}>
      <p className={styles.reportTitle}>
        {report.problem_label} · {report.link_label}
      </p>
      {report.reason && <p>{report.reason}</p>}
      {report.described_memory && <p>{report.described_memory}</p>}
      {report.candidate_keys_label && <p>Candidates {report.candidate_keys_label}</p>}
      {report.correction && <p>{report.correction}</p>}
      {report.display_created_at && <p>{report.display_created_at}</p>}
    </article>
  );
}
