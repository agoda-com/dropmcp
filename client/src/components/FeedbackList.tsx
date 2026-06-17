import type { FeedbackItem } from '../api/feedback';
import FeedbackCard from './FeedbackCard';
import styles from './FeedbackList.module.css';

interface Props {
  loading: boolean;
  error: string | null;
  items: FeedbackItem[];
  onItemUpdated: () => void;
}

export default function FeedbackList({ loading, error, items, onItemUpdated }: Props) {
  if (loading) return <div className={styles.loading}>Loading feedback…</div>;
  if (error) return <div className={styles.error}>{error}</div>;
  if (items.length === 0) return <div className={styles.empty}>No feedback entries yet.</div>;

  return (
    <div className={styles.list}>
      {items.map((item) => (
        <FeedbackCard key={item.id} item={item} onUpdated={onItemUpdated} />
      ))}
    </div>
  );
}
