import type { MemoryStatsPeriod } from '../../api/memory';
import styles from './memory.module.css';

export default function MemoryStatsStrip({
  periods,
}: {
  periods: MemoryStatsPeriod[];
}) {
  if (periods.length === 0) return null;
  return (
    <section className={styles.stats} aria-label="Recall stats">
      {periods.map((period) => (
        <article key={period.days} className={styles.statCard} aria-label={period.label}>
          <h3>{period.label}</h3>
          <p>
            Recalls <strong>{period.recall_count}</strong>
          </p>
          <p>
            Returning <strong>{period.share_returning}</strong>
          </p>
          <p>
            Reports per recall <strong>{period.reports_per_recall}</strong>
          </p>
          <p>
            Writers <strong>{period.distinct_writers}</strong>
          </p>
        </article>
      ))}
    </section>
  );
}
