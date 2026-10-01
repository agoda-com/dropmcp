import type { FeedbackItem, FeedbackStatus, FeedbackType } from '../api/feedback';
import styles from './FeedbackCard.module.css';

export default function FeedbackCardHeader({ item }: { item: FeedbackItem }) {
  return (
    <div className={styles.cardHeader}>
      <StatusBadge status={item.status} />
      <TypeBadge type={item.feedback_type ?? 'correction'} />
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

function TypeBadge({ type }: { type: FeedbackType }) {
  const typeClass =
    type === 'agent_work' ? styles.typeAgentWork : styles.typeCorrection;
  const label = type === 'agent_work' ? 'agent work' : 'correction';
  return <span className={`${styles.typeBadge} ${typeClass}`}>{label}</span>;
}
