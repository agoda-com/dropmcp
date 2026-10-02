import { useEffect, useState } from 'react';
import { fetchMemory, type MemoryDetailResponse } from '../../api/memory';
import MemoryDeleteButton from './MemoryDeleteButton';
import MemoryReportRow from './MemoryReportRow';
import styles from './memory.module.css';

export default function MemoryDetailsPanel({
  memoryKey,
  onDeleted,
}: {
  memoryKey: string;
  onDeleted: (key: string) => void;
}) {
  const [detail, setDetail] = useState<MemoryDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setError(null);
    fetchMemory(memoryKey)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [memoryKey]);

  if (error) return <p className={styles.error}>{error}</p>;
  if (!detail) return <p className={styles.loading}>Loading memory...</p>;

  return (
    <section className={styles.details} aria-label="Memory details">
      <h3>{detail.memory.title}</h3>
      <p className={styles.meta}>
        {detail.memory.key} · {detail.memory.scope}
      </p>
      <p className={styles.body}>{detail.memory.body}</p>
      {detail.memory.evidence && <p className={styles.body}>{detail.memory.evidence}</p>}
      <h4>Reports</h4>
      {detail.reports.length === 0 ? (
        <p className={styles.meta}>No reports.</p>
      ) : (
        <div className={styles.reports}>
          {detail.reports.map((report) => (
            <MemoryReportRow key={report.id} report={report} />
          ))}
        </div>
      )}
      <MemoryDeleteButton
        memoryKey={memoryKey}
        onDeleted={() => onDeleted(memoryKey)}
      />
    </section>
  );
}
