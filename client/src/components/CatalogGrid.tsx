import type { CatalogItem } from '../api/catalog';
import CatalogCard from './CatalogCard';
import styles from './CatalogGrid.module.css';

export default function CatalogGrid({ items }: { items: CatalogItem[] }) {
  return (
    <div className={styles.grid}>
      {items.map((item) => (
        <CatalogCard key={`${item.type}-${item.name}`} item={item} />
      ))}
    </div>
  );
}

export function SkeletonGrid() {
  return (
    <div className={styles.grid} aria-hidden="true">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className={styles.skeletonCard}>
          <div className={`${styles.skeletonBlock} ${styles.skeletonThumb}`} />
          <div className={styles.skeletonLines}>
            <div className={`${styles.skeletonBlock} ${styles.skeletonLine}`} />
            <div className={`${styles.skeletonBlock} ${styles.skeletonLine} ${styles.short}`} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function EmptyState() {
  return (
    <div className={styles.stateWrap}>
      <div className={styles.emptyState}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.35-4.35" />
        </svg>
        <h2>No matches</h2>
        <p>Try a different search, category, or type filter.</p>
      </div>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className={styles.stateWrap}>
      <div className={styles.errorState}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 8v4M12 16h.01" />
        </svg>
        <h2>Something went wrong</h2>
        <p>{message}</p>
      </div>
    </div>
  );
}
