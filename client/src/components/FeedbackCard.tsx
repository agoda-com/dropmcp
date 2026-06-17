import { type FeedbackItem, type FeedbackStatus } from '../api/feedback';
import FeedbackTriageRow from './FeedbackTriageRow';
import styles from './FeedbackCard.module.css';

export default function FeedbackCard({
  item,
  onUpdated,
}: {
  item: FeedbackItem;
  onUpdated: () => void;
}) {
  return (
    <article className={styles.card}>
      <CardMeta item={item} />

      <FeedbackField label="Feedback" value={item.feedback} />
      <FeedbackField label="Better instruction" value={item.better_instruction} />
      {item.suggested_skill && <FeedbackField label="Suggested skill" value={item.suggested_skill} />}

      <FeedbackTriageRow item={item} onUpdated={onUpdated} />

      {item.resolution_url && <ResolutionLink url={item.resolution_url} />}
    </article>
  );
}

function CardMeta({ item }: { item: FeedbackItem }) {
  return (
    <div className={styles.cardHeader}>
      <StatusBadge status={item.status} />
      <span className={styles.meta}>{item.created_at}</span>
      <span className={styles.meta}>model: {item.model}</span>
      {item.client && <span className={styles.meta}>client: {item.client}</span>}
      {item.skill_name && <span className={styles.meta}>skill: {item.skill_name}</span>}
      {item.repo && <span className={styles.meta}>repo: {item.repo}</span>}
    </div>
  );
}

function StatusBadge({ status }: { status: FeedbackStatus }) {
  const statusClass =
    status === 'actioned'
      ? styles.statusActioned
      : status === 'triaged'
        ? styles.statusTriaged
        : styles.statusNew;

  return <span className={`${styles.statusBadge} ${statusClass}`}>{status}</span>;
}

function FeedbackField({ label, value }: { label: string; value: string }) {
  return (
    <>
      <span className={styles.fieldLabel}>{label}</span>
      <p className={styles.fieldText}>{value}</p>
    </>
  );
}

function ResolutionLink({ url }: { url: string }) {
  return (
    <p className={styles.resolutionLink}>
      <a href={url} target="_blank" rel="noreferrer">{url}</a>
    </p>
  );
}
