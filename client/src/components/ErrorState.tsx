import styles from './StateMessage.module.css';

export default function ErrorState({ message }: { message: string }) {
  return (
    <div className={styles.stateWrap}>
      <div className={styles.errorState}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 8v4M12 16h.01" />
        </svg>
        <h2>Something went wrong</h2>
        <p>{message}</p>
      </div>
    </div>
  );
}
