import { useCallback, useRef, useEffect } from 'react';
import { formatName } from '../utils/format';
import { useCatalog } from '../context/CatalogContext';
import type { CatalogItem } from '../api/catalog';
import { subscribeGroup, unsubscribeGroup } from '../api/subscriptions';
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
  const {
    subscriptionControlsEnabled,
    subscribedGroups,
    updateGroupSubscriptions,
  } = useCatalog();

  const groupMembers = useCallback(
    (group: string) => allItems.filter((item) => item.group === group),
    [allItems],
  );

  const groupState = useCallback(
    (group: string): 'checked' | 'unchecked' | 'indeterminate' => {
      if (!subscribedGroups.includes(group)) return 'unchecked';
      const members = groupMembers(group);
      if (members.length === 0) return 'checked';
      const subscribedCount = members.filter((m) => m.subscribed).length;
      if (subscribedCount === members.length) return 'checked';
      return 'indeterminate';
    },
    [groupMembers, subscribedGroups],
  );

  const handleGroupCheckbox = async (
    group: string,
    nextChecked: boolean,
    event: React.MouseEvent,
  ) => {
    event.stopPropagation();
    const members = groupMembers(group);
    updateGroupSubscriptions(group, members, nextChecked);
    try {
      if (nextChecked) {
        await subscribeGroup(group);
      } else {
        await unsubscribeGroup(group);
      }
    } catch {
      updateGroupSubscriptions(group, members, !nextChecked);
    }
  };

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
      {groups.length > 0 && (
        <div className={styles.filterRow}>
          <span className={styles.filterLabel}>Group</span>
          <div className={styles.categories}>
            {groups.map((group) => (
              <GroupPill
                key={group}
                group={group}
                active={groupFilter === group}
                checkboxState={groupState(group)}
                showCheckbox={subscriptionControlsEnabled}
                onFilterClick={() => onGroupChange(groupFilter === group ? null : group)}
                onCheckboxToggle={(checked, event) =>
                  handleGroupCheckbox(group, checked, event)
                }
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function GroupPill({
  group,
  active,
  checkboxState,
  showCheckbox,
  onFilterClick,
  onCheckboxToggle,
}: {
  group: string;
  active: boolean;
  checkboxState: 'checked' | 'unchecked' | 'indeterminate';
  showCheckbox: boolean;
  onFilterClick: () => void;
  onCheckboxToggle: (checked: boolean, event: React.MouseEvent) => void;
}) {
  const checkboxRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (checkboxRef.current) {
      checkboxRef.current.indeterminate = checkboxState === 'indeterminate';
    }
  }, [checkboxState]);

  return (
    <button
      type="button"
      className={`${styles.pill} ${styles.groupPill} ${active ? styles.active : ''}`}
      onClick={onFilterClick}
    >
      {showCheckbox && (
        <input
          ref={checkboxRef}
          type="checkbox"
          className={styles.groupCheckbox}
          checked={checkboxState === 'checked'}
          aria-label={`Subscribe to all in ${group}`}
          onClick={(e) => {
            e.stopPropagation();
            onCheckboxToggle(checkboxState !== 'checked', e);
          }}
          onChange={() => {}}
        />
      )}
      <span>{formatName(group)}</span>
    </button>
  );
}
