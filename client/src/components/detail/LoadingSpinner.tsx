import styles from './LoadingSpinner.module.css';

interface LoadingSpinnerProps {
  label?: string;
}

export default function LoadingSpinner({ label }: LoadingSpinnerProps) {
  return (
    <div className={styles.wrap} role="status" aria-live="polite">
      <div className={styles.spinner} aria-hidden="true" />
      {label && <span className={styles.label}>{label}</span>}
    </div>
  );
}
