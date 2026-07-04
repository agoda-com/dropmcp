import { Link } from 'react-router-dom';
import styles from './FeedbackHeader.module.css';

interface Props {
  title?: string;
  description?: string;
}

export default function FeedbackHeader({
  title = 'Agent feedback',
  description = 'Corrections recorded by agents — search, filter, and triage.',
}: Props) {
  return (
    <div className={styles.headerRow}>
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      <Link to="/" className={styles.backLink}>← Back to catalog</Link>
    </div>
  );
}
