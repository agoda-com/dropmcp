import type { MemoryListItem } from '../../api/memory';
import MemoryRow from './MemoryRow';
import styles from './memory.module.css';

export default function MemoryList({
  loading,
  error,
  items,
  selectedKey,
  onSelect,
}: {
  loading: boolean;
  error: string | null;
  items: MemoryListItem[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
}) {
  if (loading) return <div className={styles.loading}>Loading memories...</div>;
  if (error) return <div className={styles.error}>{error}</div>;
  if (items.length === 0) {
    return <div className={styles.empty}>No memories.</div>;
  }

  return (
    <div className={styles.list}>
      {items.map((item) => (
        <MemoryRow
          key={item.key}
          item={item}
          selected={item.key === selectedKey}
          onSelect={() => onSelect(item.key)}
        />
      ))}
    </div>
  );
}
