import type { FeedbackDetails } from '../api/feedback';
import FeedbackArtifactList from './FeedbackArtifactList';
import styles from './FeedbackDetailsPanel.module.css';

export default function FeedbackDetailsPanel({
  details,
}: {
  details: FeedbackDetails;
}) {
  const artifacts = Array.isArray(details.artifacts) ? details.artifacts : [];
  const remaining = detailsWithoutArtifacts(details);

  return (
    <details className={styles.detailsPanel}>
      <summary>
        Details
        {artifacts.length > 0 && (
          <span>
            {artifacts.length} artifact{artifacts.length === 1 ? '' : 's'}
          </span>
        )}
      </summary>

      <div className={styles.detailsBody}>
        {details.summary && (
          <p className={styles.detailSummary}>{details.summary}</p>
        )}
        {details.work_type && (
          <p className={styles.detailMeta}>
            <span>work type</span>
            {details.work_type}
          </p>
        )}

        {artifacts.length > 0 && <FeedbackArtifactList artifacts={artifacts} />}

        {Object.keys(remaining).length > 0 && (
          <pre className={styles.detailsJson}>{JSON.stringify(remaining, null, 2)}</pre>
        )}
      </div>
    </details>
  );
}

function detailsWithoutArtifacts(details: FeedbackDetails): Record<string, unknown> {
  const {
    artifacts: _artifacts,
    summary: _summary,
    work_type: _workType,
    ...rest
  } = details;
  return rest;
}
