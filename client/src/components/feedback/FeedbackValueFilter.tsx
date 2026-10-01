import styles from './FeedbackToolbar.module.css';

interface Props {
  label: string;
  values: string[];
  selected: string | null;
  onChange: (value: string | null) => void;
}

export default function FeedbackValueFilter({ label, values, selected, onChange }: Props) {
  return (
    <div className={styles.filterRow}>
      <span className={styles.filterLabel}>{label}</span>
      <button
        type="button"
        className={`${styles.pill} ${selected === null ? styles.pillActive : ''}`}
        onClick={() => onChange(null)}
      >
        All
      </button>
      {values.map((value) => (
        <button
          key={value}
          type="button"
          className={`${styles.pill} ${selected === value ? styles.pillActive : ''}`}
          onClick={() => onChange(selected === value ? null : value)}
        >
          {value}
        </button>
      ))}
    </div>
  );
}
