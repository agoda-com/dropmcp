import {
  type FeedbackArtifact,
  type FeedbackDetails,
} from '../api/feedback';
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

        {artifacts.length > 0 && <ArtifactList artifacts={artifacts} />}

        {Object.keys(remaining).length > 0 && (
          <pre className={styles.detailsJson}>{JSON.stringify(remaining, null, 2)}</pre>
        )}
      </div>
    </details>
  );
}

function ArtifactList({ artifacts }: { artifacts: FeedbackArtifact[] }) {
  return (
    <div className={styles.artifacts}>
      {artifacts.map((artifact, index) => (
        <ArtifactBlock
          key={`${artifact.path ?? artifact.kind ?? 'artifact'}-${index}`}
          artifact={artifact}
        />
      ))}
    </div>
  );
}

function ArtifactBlock({ artifact }: { artifact: FeedbackArtifact }) {
  return (
    <section className={styles.artifactBlock}>
      <div className={styles.artifactHeader}>
        <strong>{artifact.path || 'artifact'}</strong>
        <span>{artifact.language || 'plain text'}</span>
        {artifact.kind && <span>{artifact.kind}</span>}
        {artifact.action && <span>{artifact.action}</span>}
      </div>
      {artifact.content && (
        <pre className={styles.artifactContent}>
          <code>{artifact.content}</code>
        </pre>
      )}
    </section>
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
