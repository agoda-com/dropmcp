import styles from '../StateMessage.module.css';

export default function CatalogNoMatches() {
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
