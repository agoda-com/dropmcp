import styles from './FeedbackCard.module.css';

export default function FeedbackResolutionLink({ url }: { url: string }) {
  return (
    <p className={styles.resolutionLink}>
      <a href={url} target="_blank" rel="noreferrer">{url}</a>
    </p>
  );
}
