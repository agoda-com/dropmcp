import styles from './FeedbackToolbar.module.css';

interface Props {
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
}

export default function FeedbackSearchField({ value, placeholder, onChange }: Props) {
  return (
    <div className={styles.searchWrap}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="11" cy="11" r="7" />
        <path d="M21 21l-4.35-4.35" />
      </svg>
      <input
        type="search"
        className={styles.searchInput}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
