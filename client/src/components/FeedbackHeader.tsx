import { Link } from 'react-router-dom';
import styles from './FeedbackHeader.module.css';

export default function FeedbackHeader() {
  return (
    <div className={styles.headerRow}>
      <div>
        <h2>Agent feedback</h2>
        <p>Corrections recorded by agents — search, filter, and triage.</p>
      </div>
      <Link to="/" className={styles.backLink}>← Back to catalog</Link>
    </div>
  );
}
