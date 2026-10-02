import type { MemoryListItem } from '../../api/memory';
import styles from './memory.module.css';

export default function MemoryRow({
  item,
  selected,
  onSelect,
}: {
  item: MemoryListItem;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <article
      className={selected ? styles.rowSelected : styles.row}
      aria-label={item.title}
    >
      <button type="button" className={styles.titleButton} onClick={onSelect}>
        {item.title}
      </button>
      {item.hidden_label && (
        <span className={styles.hiddenBadge}>{item.hidden_label}</span>
      )}
      <p className={styles.meta}>
        {item.key} · {item.scope} · {item.confirmations_label} · {item.open_reports_label}
      </p>
    </article>
  );
}
