import styles from './CatalogGrid.module.css';

export default function CatalogSkeletonGrid() {
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
