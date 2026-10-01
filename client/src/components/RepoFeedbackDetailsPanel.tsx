import type { RepoFeedbackDetails } from '../api/repoFeedback';
import styles from './FeedbackDetailsPanel.module.css';

export default function RepoFeedbackDetailsPanel({ details }: { details: RepoFeedbackDetails }) {
  return (
    <details className={styles.detailsPanel}>
      <summary>Details</summary>
      <div className={styles.detailsBody}>
        <pre className={styles.detailsJson}>
          {JSON.stringify(details, null, 2)}
        </pre>
      </div>
    </details>
  );
}
