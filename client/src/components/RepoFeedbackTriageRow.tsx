import { useState } from 'react';
import {
  REPO_FEEDBACK_STATUSES,
  patchRepoFeedback,
  type RepoFeedbackItem,
  type RepoFeedbackStatus,
} from '../api/repoFeedback';
import styles from './FeedbackTriageRow.module.css';

export default function RepoFeedbackTriageRow({
  item,
  onUpdated,
}: {
  item: RepoFeedbackItem;
  onUpdated: () => void;
}) {
  const [status, setStatus] = useState(item.status);
  const [resolutionUrl, setResolutionUrl] = useState(item.resolution_url ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await patchRepoFeedback(item.id, {
        status,
        resolution_url: resolutionUrl.trim() || null,
      });
      onUpdated();
    } catch (err) {
      console.error('Failed to save repo feedback triage state:', err);
      setError(err instanceof Error ? err.message : 'Failed to save changes.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.triageRow}>
      <label className={styles.triageField}>
        <span className={styles.fieldLabel}>Status</span>
        <select
          className={styles.select}
          value={status}
          onChange={(e) => setStatus(e.target.value as RepoFeedbackStatus)}
        >
          {REPO_FEEDBACK_STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </label>
      <label className={`${styles.triageField} ${styles.triageFieldWide}`}>
        <span className={styles.fieldLabel}>Resolution URL</span>
        <input
          type="url"
          className={styles.textInput}
          placeholder="https://..."
          value={resolutionUrl}
          onChange={(e) => setResolutionUrl(e.target.value)}
        />
      </label>
      <button type="button" className={styles.saveBtn} disabled={saving} onClick={handleSave}>
        {saving ? 'Saving...' : 'Save'}
      </button>
      {error && <p className={styles.saveError} role="alert">{error}</p>}
    </div>
  );
}
