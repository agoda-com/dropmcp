import styles from './SearchToolbar.module.css';

interface Props {
  search: string;
  onSearchChange: (value: string) => void;
  typeFilter: string;
  onTypeChange: (type: string) => void;
  categories: string[];
  categoryFilter: string | null;
  onCategoryChange: (cat: string | null) => void;
}

function formatName(kebab: string): string {
  return kebab
    .split('-')
    .map((w) => (w.length ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : ''))
    .join(' ');
}

export default function SearchToolbar({
  search,
  onSearchChange,
  typeFilter,
  onTypeChange,
  categories,
  categoryFilter,
  onCategoryChange,
}: Props) {
  return (
    <div className={styles.toolbar}>
      <div className={styles.searchWrap}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.35-4.35" />
        </svg>
        <input
          type="search"
          className={styles.searchInput}
          placeholder="Search by name or description…"
          autoComplete="off"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>
      <div className={styles.filterRow}>
        <span className={styles.filterLabel}>Type</span>
        <div className={styles.typeFilters}>
          {['all', 'skill', 'prompt'].map((t) => (
            <button
              key={t}
              type="button"
              className={`${styles.pill} ${typeFilter === t ? styles.active : ''}`}
              onClick={() => onTypeChange(t)}
            >
              {t === 'all' ? 'All' : t === 'skill' ? 'Skills' : 'Prompts'}
            </button>
          ))}
        </div>
      </div>
      {categories.length > 0 && (
        <div className={styles.filterRow}>
          <span className={styles.filterLabel}>Category</span>
          <div className={styles.categories}>
            {categories.map((cat) => (
              <button
                key={cat}
                type="button"
                className={`${styles.pill} ${categoryFilter === cat ? styles.active : ''}`}
                onClick={() => onCategoryChange(categoryFilter === cat ? null : cat)}
              >
                {formatName(cat)}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
