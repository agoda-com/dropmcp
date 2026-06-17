import { useState } from 'react';
import {
  FEEDBACK_STATUSES,
  patchFeedback,
  type FeedbackItem,
  type FeedbackStatus,
} from '../api/feedback';
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

      <FeedbackField label="Confession" value={item.confession} />
      <FeedbackField label="Better instruction" value={item.better_instruction} />
      {item.suggested_skill && <FeedbackField label="Suggested skill" value={item.suggested_skill} />}

      <TriageRow item={item} onUpdated={onUpdated} />

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

function TriageRow({ item, onUpdated }: { item: FeedbackItem; onUpdated: () => void }) {
  const [status, setStatus] = useState(item.status);
  const [resolutionUrl, setResolutionUrl] = useState(item.resolution_url ?? '');
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await patchFeedback(item.id, {
        status,
        resolution_url: resolutionUrl.trim() || null,
      });
      onUpdated();
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
          onChange={(e) => setStatus(e.target.value as FeedbackStatus)}
        >
          {FEEDBACK_STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </label>
      <label className={`${styles.triageField} ${styles.triageFieldWide}`}>
        <span className={styles.fieldLabel}>Resolution URL</span>
        <input
          type="url"
          className={styles.textInput}
          placeholder="https://…"
          value={resolutionUrl}
          onChange={(e) => setResolutionUrl(e.target.value)}
        />
      </label>
      <button type="button" className={styles.saveBtn} disabled={saving} onClick={handleSave}>
        {saving ? 'Saving…' : 'Save'}
      </button>
    </div>
  );
}

function ResolutionLink({ url }: { url: string }) {
  return (
    <p className={styles.resolutionLink}>
      <a href={url} target="_blank" rel="noreferrer">{url}</a>
    </p>
  );
}
