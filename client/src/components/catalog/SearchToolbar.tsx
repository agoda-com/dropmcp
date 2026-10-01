import { useCatalog } from '../../context/CatalogContext';
import { formatName } from '../../utils/format';
import type { CatalogItem } from '../../api/catalog';
import GroupSubscriptionFilter from './GroupSubscriptionFilter';
import styles from './SearchToolbar.module.css';

interface Props {
  search: string;
  onSearchChange: (value: string) => void;
  typeFilter: string;
  onTypeChange: (type: string) => void;
  categories: string[];
  categoryFilter: string | null;
  onCategoryChange: (cat: string | null) => void;
  groups: string[];
  groupFilter: string | null;
  onGroupChange: (group: string | null) => void;
  allItems: CatalogItem[];
}

export default function SearchToolbar({
  search,
  onSearchChange,
  typeFilter,
  onTypeChange,
  categories,
  categoryFilter,
  onCategoryChange,
  groups,
  groupFilter,
  onGroupChange,
  allItems,
}: Props) {
  const { subscriptionsEnabled } = useCatalog();

  return (
    <div className={styles.toolbar}>
      <SearchField value={search} onChange={onSearchChange} />
      <TypeFilter value={typeFilter} onChange={onTypeChange} />
      {categories.length > 0 && (
        <ToggleFilter
          label="Category"
          values={categories}
          selected={categoryFilter}
          onChange={onCategoryChange}
        />
      )}
      {groups.length > 0 && (
        <ToggleFilter
          label="Group"
          values={groups}
          selected={groupFilter}
          onChange={onGroupChange}
        />
      )}
      {subscriptionsEnabled && groups.length > 0 && (
        <GroupSubscriptionFilter groups={groups} allItems={allItems} />
      )}
    </div>
  );
}

function SearchField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
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
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

function TypeFilter({ value, onChange }: { value: string; onChange: (type: string) => void }) {
  return (
    <div className={styles.filterRow}>
      <span className={styles.filterLabel}>Type</span>
      <div className={styles.typeFilters}>
        {['all', 'skill', 'prompt'].map((t) => (
          <button
            key={t}
            type="button"
            className={`${styles.pill} ${value === t ? styles.active : ''}`}
            onClick={() => onChange(t)}
          >
            {t === 'all' ? 'All' : t === 'skill' ? 'Skills' : 'Prompts'}
          </button>
        ))}
      </div>
    </div>
  );
}

function ToggleFilter({
  label,
  values,
  selected,
  onChange,
}: {
  label: string;
  values: string[];
  selected: string | null;
  onChange: (value: string | null) => void;
}) {
  return (
    <div className={styles.filterRow}>
      <span className={styles.filterLabel}>{label}</span>
      <div className={styles.categories}>
        {values.map((value) => (
          <button
            key={value}
            type="button"
            className={`${styles.pill} ${selected === value ? styles.active : ''}`}
            onClick={() => onChange(selected === value ? null : value)}
          >
            {formatName(value)}
          </button>
        ))}
      </div>
    </div>
  );
}
