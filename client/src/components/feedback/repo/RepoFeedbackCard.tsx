import type { RepoFeedbackDetails, RepoFeedbackItem } from '../../../api/repoFeedback';
import FeedbackField from '../FeedbackField';
import FeedbackResolutionLink from '../FeedbackResolutionLink';
import RepoFeedbackCardHeader from './RepoFeedbackCardHeader';
import RepoFeedbackDetailsPanel from './RepoFeedbackDetailsPanel';
import RepoFeedbackTriageRow from './RepoFeedbackTriageRow';
import styles from '../FeedbackCard.module.css';

export default function RepoFeedbackCard({
  item,
  onUpdated,
}: {
  item: RepoFeedbackItem;
  onUpdated: () => void;
}) {
  return (
    <article className={styles.card}>
      <RepoFeedbackCardHeader item={item} />

      <FeedbackField label="Summary" value={item.summary} />
      <FeedbackField label="Impact" value={item.impact} />
      {item.suggested_fix && (
        <FeedbackField label="Suggested fix" value={item.suggested_fix} />
      )}
      {hasDetails(item.details) && <RepoFeedbackDetailsPanel details={item.details} />}

      <RepoFeedbackTriageRow item={item} onUpdated={onUpdated} />

      {item.resolution_url && <FeedbackResolutionLink url={item.resolution_url} />}
    </article>
  );
}

function hasDetails(details: RepoFeedbackItem['details']): details is RepoFeedbackDetails {
  return Boolean(details && Object.keys(details).length > 0);
}
