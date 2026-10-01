import type { FeedbackDetails, FeedbackItem } from '../api/feedback';
import FeedbackCardHeader from './FeedbackCardHeader';
import FeedbackDetailsPanel from './FeedbackDetailsPanel';
import FeedbackField from './FeedbackField';
import FeedbackResolutionLink from './FeedbackResolutionLink';
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
      <FeedbackCardHeader item={item} />

      <FeedbackField label="Feedback" value={item.feedback} />
      <FeedbackField label="Better instruction" value={item.better_instruction} />
      {item.suggested_skill && (
        <FeedbackField label="Suggested skill" value={item.suggested_skill} />
      )}
      {hasDetails(item.details) && <FeedbackDetailsPanel details={item.details} />}

      <FeedbackTriageRow item={item} onUpdated={onUpdated} />

      {item.resolution_url && <FeedbackResolutionLink url={item.resolution_url} />}
    </article>
  );
}

function hasDetails(details: FeedbackItem['details']): details is FeedbackDetails {
  return Boolean(details && Object.keys(details).length > 0);
}
