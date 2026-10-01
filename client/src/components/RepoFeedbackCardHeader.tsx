import type {
  RepoFeedbackCategory,
  RepoFeedbackItem,
  RepoFeedbackStatus,
} from '../api/repoFeedback';
import { formatLabel } from '../utils/format';
import styles from './FeedbackCard.module.css';

export default function RepoFeedbackCardHeader({ item }: { item: RepoFeedbackItem }) {
  return (
    <div className={styles.cardHeader}>
      <StatusBadge status={item.status} />
      <CategoryBadge category={item.category} />
      <span className={styles.meta}>occurrences: {item.occurrence_count}</span>
      <span className={styles.meta}>repo: {item.repo}</span>
      <span className={styles.meta}>last seen: {item.last_seen_at}</span>
      <span className={styles.meta}>model: {item.model}</span>
      {item.client && <span className={styles.meta}>client: {item.client}</span>}
    </div>
  );
}

function StatusBadge({ status }: { status: RepoFeedbackStatus }) {
  const statusClass =
    status === 'actioned'
      ? styles.statusActioned
      : status === 'triaged'
        ? styles.statusTriaged
        : status === 'wontfix'
          ? styles.statusWontfix
          : styles.statusNew;

  return <span className={`${styles.statusBadge} ${statusClass}`}>{status}</span>;
}

function CategoryBadge({ category }: { category: RepoFeedbackCategory }) {
  return (
    <span className={`${styles.typeBadge} ${styles.typeCorrection}`}>
      {formatLabel(category)}
    </span>
  );
}
