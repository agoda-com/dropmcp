import type { RepoFeedbackItem } from '../../../api/repoFeedback';
import RepoFeedbackCard from './RepoFeedbackCard';
import styles from '../FeedbackList.module.css';

export default function RepoFeedbackList({
  loading,
  error,
  items,
  onItemUpdated,
}: {
  loading: boolean;
  error: string | null;
  items: RepoFeedbackItem[];
  onItemUpdated: () => void;
}) {
  if (loading) return <div className={styles.loading}>Loading repo feedback...</div>;
  if (error) return <div className={styles.error}>{error}</div>;
  if (items.length === 0) {
    return <div className={styles.empty}>No repo feedback entries yet.</div>;
  }

  return (
    <div className={styles.list}>
      {items.map((item) => (
        <RepoFeedbackCard key={item.id} item={item} onUpdated={onItemUpdated} />
      ))}
    </div>
  );
}
