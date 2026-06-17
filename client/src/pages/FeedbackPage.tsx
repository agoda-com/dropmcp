import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchFeedback,
  patchFeedback,
  type FeedbackItem,
  type FeedbackStatus,
} from '../api/feedback';
import styles from './FeedbackPage.module.css';

const STATUSES: FeedbackStatus[] = ['new', 'triaged', 'actioned'];

export default function FeedbackPage() {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<FeedbackStatus | 'all'>('all');
  const [modelFilter, setModelFilter] = useState<string | null>(null);
  const [clientFilter, setClientFilter] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchFeedback({
        search: search.trim() || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter,
        model: modelFilter ?? undefined,
        client: clientFilter ?? undefined,
      });
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load feedback.');
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, modelFilter, clientFilter]);

  useEffect(() => {
    const timer = setTimeout(load, search ? 250 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  const models = useMemo(() => {
    const set = new Set<string>();
    items.forEach((i) => { if (i.model) set.add(i.model); });
    return Array.from(set).sort();
  }, [items]);

  const clients = useMemo(() => {
    const set = new Set<string>();
    items.forEach((i) => { if (i.client) set.add(i.client); });
    return Array.from(set).sort();
  }, [items]);

  return (
    <main className={styles.feedbackPage}>
      <div className={styles.headerRow}>
        <div>
          <h2>Agent feedback</h2>
          <p>Corrections recorded by agents — search, filter, and triage.</p>
        </div>
        <Link to="/" className={styles.backLink}>← Back to catalog</Link>
      </div>

      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
          <input
            type="search"
            className={styles.searchInput}
            placeholder="Search confession or better instruction…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className={styles.filterRow}>
          <span className={styles.filterLabel}>Status</span>
          {(['all', ...STATUSES] as const).map((s) => (
            <button
              key={s}
              type="button"
              className={`${styles.pill} ${statusFilter === s ? styles.pillActive : ''}`}
              onClick={() => setStatusFilter(s)}
            >
              {s === 'all' ? 'All' : s}
            </button>
          ))}
        </div>

        {models.length > 0 && (
          <div className={styles.filterRow}>
            <span className={styles.filterLabel}>Model</span>
            <button
              type="button"
              className={`${styles.pill} ${modelFilter === null ? styles.pillActive : ''}`}
              onClick={() => setModelFilter(null)}
            >
              All
            </button>
            {models.map((m) => (
              <button
                key={m}
                type="button"
                className={`${styles.pill} ${modelFilter === m ? styles.pillActive : ''}`}
                onClick={() => setModelFilter(modelFilter === m ? null : m)}
              >
                {m}
              </button>
            ))}
          </div>
        )}

        {clients.length > 0 && (
          <div className={styles.filterRow}>
            <span className={styles.filterLabel}>Client</span>
            <button
              type="button"
              className={`${styles.pill} ${clientFilter === null ? styles.pillActive : ''}`}
              onClick={() => setClientFilter(null)}
            >
              All
            </button>
            {clients.map((c) => (
              <button
                key={c}
                type="button"
                className={`${styles.pill} ${clientFilter === c ? styles.pillActive : ''}`}
                onClick={() => setClientFilter(clientFilter === c ? null : c)}
              >
                {c}
              </button>
            ))}
          </div>
        )}
      </div>

      {loading && <div className={styles.loading}>Loading feedback…</div>}
      {!loading && error && <div className={styles.error}>{error}</div>}
      {!loading && !error && items.length === 0 && (
        <div className={styles.empty}>No feedback entries yet.</div>
      )}
      {!loading && !error && items.length > 0 && (
        <div className={styles.list}>
          {items.map((item) => (
            <FeedbackCard key={item.id} item={item} onUpdated={load} />
          ))}
        </div>
      )}
    </main>
  );
}

function FeedbackCard({
  item,
  onUpdated,
}: {
  item: FeedbackItem;
  onUpdated: () => void;
}) {
  const [status, setStatus] = useState(item.status);
  const [resolutionUrl, setResolutionUrl] = useState(item.resolution_url ?? '');
  const [saving, setSaving] = useState(false);

  const statusClass =
    item.status === 'actioned'
      ? styles.statusActioned
      : item.status === 'triaged'
        ? styles.statusTriaged
        : styles.statusNew;

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
    <article className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={`${styles.statusBadge} ${statusClass}`}>{item.status}</span>
        <span className={styles.meta}>{item.created_at}</span>
        <span className={styles.meta}>model: {item.model}</span>
        {item.client && <span className={styles.meta}>client: {item.client}</span>}
        {item.skill_name && <span className={styles.meta}>skill: {item.skill_name}</span>}
        {item.repo && <span className={styles.meta}>repo: {item.repo}</span>}
      </div>

      <span className={styles.fieldLabel}>Confession</span>
      <p className={styles.fieldText}>{item.confession}</p>

      <span className={styles.fieldLabel}>Better instruction</span>
      <p className={styles.fieldText}>{item.better_instruction}</p>

      {item.suggested_skill && (
        <>
          <span className={styles.fieldLabel}>Suggested skill</span>
          <p className={styles.fieldText}>{item.suggested_skill}</p>
        </>
      )}

      <div className={styles.triageRow}>
        <label className={styles.triageField}>
          <span className={styles.fieldLabel}>Status</span>
          <select
            className={styles.select}
            value={status}
            onChange={(e) => setStatus(e.target.value as FeedbackStatus)}
          >
            {STATUSES.map((s) => (
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
        <button
          type="button"
          className={styles.saveBtn}
          disabled={saving}
          onClick={handleSave}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>

      {item.resolution_url && (
        <p className={styles.resolutionLink}>
          <a href={item.resolution_url} target="_blank" rel="noreferrer">
            {item.resolution_url}
          </a>
        </p>
      )}
    </article>
  );
}
