import type { FeedbackArtifact } from '../api/feedback';
import styles from './FeedbackDetailsPanel.module.css';

export default function FeedbackArtifactList({ artifacts }: { artifacts: FeedbackArtifact[] }) {
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
