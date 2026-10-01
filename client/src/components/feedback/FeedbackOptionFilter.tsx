import styles from './FeedbackToolbar.module.css';

interface Props<T extends string> {
  label: string;
  options: readonly T[];
  value: T;
  optionLabel: (option: T) => string;
  onChange: (option: T) => void;
}

export default function FeedbackOptionFilter<T extends string>({
  label,
  options,
  value,
  optionLabel,
  onChange,
}: Props<T>) {
  return (
    <div className={styles.filterRow}>
      <span className={styles.filterLabel}>{label}</span>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          className={`${styles.pill} ${value === option ? styles.pillActive : ''}`}
          onClick={() => onChange(option)}
        >
          {optionLabel(option)}
        </button>
      ))}
    </div>
  );
}
