import styles from './FeedbackCard.module.css';

export default function FeedbackField({ label, value }: { label: string; value: string }) {
  return (
    <>
      <span className={styles.fieldLabel}>{label}</span>
      <p className={styles.fieldText}>{value}</p>
    </>
  );
}
