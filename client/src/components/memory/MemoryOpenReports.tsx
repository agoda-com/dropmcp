import type { MemoryReport } from '../../api/memory';
import MemoryReportRow from './MemoryReportRow';
import styles from './memory.module.css';

export default function MemoryOpenReports({ reports }: { reports: MemoryReport[] }) {
  return (
    <section className={styles.openReports} aria-label="Open reports">
      <h3>Open reports</h3>
      {reports.length === 0 ? (
        <p className={styles.meta}>No open reports.</p>
      ) : (
        <div className={styles.reports}>
          {reports.map((report) => (
            <MemoryReportRow key={report.id} report={report} />
          ))}
        </div>
      )}
    </section>
  );
}
