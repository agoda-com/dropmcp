import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  REPO_FEEDBACK_CATEGORIES,
  REPO_FEEDBACK_STATUSES,
  fetchRepoFeedback,
  patchRepoFeedback,
  type RepoFeedbackCategory,
  type RepoFeedbackDetails,
  type RepoFeedbackItem,
  type RepoFeedbackStatus,
} from '../api/repoFeedback';
import FeedbackHeader from '../components/FeedbackHeader';
import pageStyles from './FeedbackPage.module.css';
import toolbarStyles from '../components/FeedbackToolbar.module.css';
import listStyles from '../components/FeedbackList.module.css';
import cardStyles from '../components/FeedbackCard.module.css';
import triageStyles from '../components/FeedbackTriageRow.module.css';
import detailsStyles from '../components/FeedbackDetailsPanel.module.css';

type SortMode = 'priority' | 'recent';

export default function RepoFeedbackPage() {
  const [items, setItems] = useState<RepoFeedbackItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<RepoFeedbackStatus | 'all'>('all');
  const [categoryFilter, setCategoryFilter] = useState<RepoFeedbackCategory | 'all'>('all');
  const [repoFilter, setRepoFilter] = useState<string | null>(null);
  const [modelFilter, setModelFilter] = useState<string | null>(null);
  const [clientFilter, setClientFilter] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>('priority');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchRepoFeedback({
        search: search.trim() || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter,
        category: categoryFilter === 'all' ? undefined : categoryFilter,
        repo: repoFilter ?? undefined,
        model: modelFilter ?? undefined,
        client: clientFilter ?? undefined,
        sort: sortMode,
      });
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load repo feedback.');
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, categoryFilter, repoFilter, modelFilter, clientFilter, sortMode]);

  useEffect(() => {
    const timer = setTimeout(load, search ? 250 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  const repos = useMemo(() => uniqueValues(items, (item) => item.repo), [items]);
  const models = useMemo(() => uniqueValues(items, (item) => item.model), [items]);
  const clients = useMemo(() => uniqueValues(items, (item) => item.client), [items]);

  return (
    <main className={pageStyles.feedbackPage}>
      <FeedbackHeader
        title="Repo feedback"
        description="Repository friction recorded by agents - search, filter, and triage."
      />

      <RepoFeedbackToolbar
        search={search}
        onSearchChange={setSearch}
        statusFilter={statusFilter}
        onStatusChange={setStatusFilter}
        categoryFilter={categoryFilter}
        onCategoryChange={setCategoryFilter}
        repoFilter={repoFilter}
        repos={repos}
        onRepoChange={setRepoFilter}
        sortMode={sortMode}
        onSortChange={setSortMode}
        models={models}
        modelFilter={modelFilter}
        onModelChange={setModelFilter}
        clients={clients}
        clientFilter={clientFilter}
        onClientChange={setClientFilter}
      />

      <RepoFeedbackList
        loading={loading}
        error={error}
        items={items}
        onItemUpdated={load}
      />
    </main>
  );
}

function RepoFeedbackToolbar({
  search,
  onSearchChange,
  statusFilter,
  onStatusChange,
  categoryFilter,
  onCategoryChange,
  repoFilter,
  repos,
  onRepoChange,
  sortMode,
  onSortChange,
  models,
  modelFilter,
  onModelChange,
  clients,
  clientFilter,
  onClientChange,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: RepoFeedbackStatus | 'all';
  onStatusChange: (status: RepoFeedbackStatus | 'all') => void;
  categoryFilter: RepoFeedbackCategory | 'all';
  onCategoryChange: (category: RepoFeedbackCategory | 'all') => void;
  repoFilter: string | null;
  repos: string[];
  onRepoChange: (repo: string | null) => void;
  sortMode: SortMode;
  onSortChange: (sort: SortMode) => void;
  models: string[];
  modelFilter: string | null;
  onModelChange: (model: string | null) => void;
  clients: string[];
  clientFilter: string | null;
  onClientChange: (client: string | null) => void;
}) {
  return (
    <div className={toolbarStyles.toolbar}>
      <SearchField value={search} onChange={onSearchChange} />
      <StatusFilter value={statusFilter} onChange={onStatusChange} />
      <CategoryFilter value={categoryFilter} onChange={onCategoryChange} />
      <SortFilter value={sortMode} onChange={onSortChange} />

      {repos.length > 0 && (
        <ValueFilter
          label="Repo"
          values={repos}
          selected={repoFilter}
          onChange={onRepoChange}
        />
      )}

      {models.length > 0 && (
        <ValueFilter
          label="Model"
          values={models}
          selected={modelFilter}
          onChange={onModelChange}
        />
      )}

      {clients.length > 0 && (
        <ValueFilter
          label="Client"
          values={clients}
          selected={clientFilter}
          onChange={onClientChange}
        />
      )}
    </div>
  );
}

function SearchField({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className={toolbarStyles.searchWrap}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="11" cy="11" r="7" />
        <path d="M21 21l-4.35-4.35" />
      </svg>
      <input
        type="search"
        className={toolbarStyles.searchInput}
        placeholder="Search summary or impact..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

function StatusFilter({
  value,
  onChange,
}: {
  value: RepoFeedbackStatus | 'all';
  onChange: (status: RepoFeedbackStatus | 'all') => void;
}) {
  return (
    <div className={toolbarStyles.filterRow}>
      <span className={toolbarStyles.filterLabel}>Status</span>
      {(['all', ...REPO_FEEDBACK_STATUSES] as const).map((status) => (
        <button
          key={status}
          type="button"
          className={`${toolbarStyles.pill} ${value === status ? toolbarStyles.pillActive : ''}`}
          onClick={() => onChange(status)}
        >
          {status === 'all' ? 'All' : status}
        </button>
      ))}
    </div>
  );
}

function CategoryFilter({
  value,
  onChange,
}: {
  value: RepoFeedbackCategory | 'all';
  onChange: (category: RepoFeedbackCategory | 'all') => void;
}) {
  return (
    <div className={toolbarStyles.filterRow}>
      <span className={toolbarStyles.filterLabel}>Category</span>
      {(['all', ...REPO_FEEDBACK_CATEGORIES] as const).map((category) => (
        <button
          key={category}
          type="button"
          className={`${toolbarStyles.pill} ${value === category ? toolbarStyles.pillActive : ''}`}
          onClick={() => onChange(category)}
        >
          {category === 'all' ? 'All' : formatLabel(category)}
        </button>
      ))}
    </div>
  );
}

function SortFilter({
  value,
  onChange,
}: {
  value: SortMode;
  onChange: (sort: SortMode) => void;
}) {
  return (
    <div className={toolbarStyles.filterRow}>
      <span className={toolbarStyles.filterLabel}>Sort</span>
      {(['priority', 'recent'] as const).map((sort) => (
        <button
          key={sort}
          type="button"
          className={`${toolbarStyles.pill} ${value === sort ? toolbarStyles.pillActive : ''}`}
          onClick={() => onChange(sort)}
        >
          {sort === 'priority' ? 'Priority' : 'Recent'}
        </button>
      ))}
    </div>
  );
}

function ValueFilter({
  label,
  values,
  selected,
  onChange,
}: {
  label: string;
  values: string[];
  selected: string | null;
  onChange: (value: string | null) => void;
}) {
  return (
    <div className={toolbarStyles.filterRow}>
      <span className={toolbarStyles.filterLabel}>{label}</span>
      <button
        type="button"
        className={`${toolbarStyles.pill} ${selected === null ? toolbarStyles.pillActive : ''}`}
        onClick={() => onChange(null)}
      >
        All
      </button>
      {values.map((value) => (
        <button
          key={value}
          type="button"
          className={`${toolbarStyles.pill} ${selected === value ? toolbarStyles.pillActive : ''}`}
          onClick={() => onChange(selected === value ? null : value)}
        >
          {value}
        </button>
      ))}
    </div>
  );
}

function RepoFeedbackList({
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
  if (loading) return <div className={listStyles.loading}>Loading repo feedback...</div>;
  if (error) return <div className={listStyles.error}>{error}</div>;
  if (items.length === 0) {
    return <div className={listStyles.empty}>No repo feedback entries yet.</div>;
  }

  return (
    <div className={listStyles.list}>
      {items.map((item) => (
        <RepoFeedbackCard key={item.id} item={item} onUpdated={onItemUpdated} />
      ))}
    </div>
  );
}

function RepoFeedbackCard({
  item,
  onUpdated,
}: {
  item: RepoFeedbackItem;
  onUpdated: () => void;
}) {
  return (
    <article className={cardStyles.card}>
      <RepoFeedbackMeta item={item} />

      <FeedbackField label="Summary" value={item.summary} />
      <FeedbackField label="Impact" value={item.impact} />
      {item.suggested_fix && (
        <FeedbackField label="Suggested fix" value={item.suggested_fix} />
      )}
      {hasDetails(item.details) && <RepoDetailsPanel details={item.details} />}

      <RepoFeedbackTriageRow item={item} onUpdated={onUpdated} />

      {item.resolution_url && <ResolutionLink url={item.resolution_url} />}
    </article>
  );
}

function RepoFeedbackMeta({ item }: { item: RepoFeedbackItem }) {
  return (
    <div className={cardStyles.cardHeader}>
      <StatusBadge status={item.status} />
      <CategoryBadge category={item.category} />
      <span className={cardStyles.meta}>occurrences: {item.occurrence_count}</span>
      <span className={cardStyles.meta}>repo: {item.repo}</span>
      <span className={cardStyles.meta}>last seen: {item.last_seen_at}</span>
      <span className={cardStyles.meta}>model: {item.model}</span>
      {item.client && <span className={cardStyles.meta}>client: {item.client}</span>}
    </div>
  );
}

function StatusBadge({ status }: { status: RepoFeedbackStatus }) {
  const statusClass =
    status === 'actioned'
      ? cardStyles.statusActioned
      : status === 'triaged'
        ? cardStyles.statusTriaged
        : status === 'wontfix'
          ? cardStyles.statusWontfix
          : cardStyles.statusNew;

  return <span className={`${cardStyles.statusBadge} ${statusClass}`}>{status}</span>;
}

function CategoryBadge({ category }: { category: RepoFeedbackCategory }) {
  return (
    <span className={`${cardStyles.typeBadge} ${cardStyles.typeCorrection}`}>
      {formatLabel(category)}
    </span>
  );
}

function FeedbackField({ label, value }: { label: string; value: string }) {
  return (
    <>
      <span className={cardStyles.fieldLabel}>{label}</span>
      <p className={cardStyles.fieldText}>{value}</p>
    </>
  );
}

function RepoDetailsPanel({ details }: { details: RepoFeedbackDetails }) {
  return (
    <details className={detailsStyles.detailsPanel}>
      <summary>Details</summary>
      <div className={detailsStyles.detailsBody}>
        <pre className={detailsStyles.detailsJson}>
          {JSON.stringify(details, null, 2)}
        </pre>
      </div>
    </details>
  );
}

function RepoFeedbackTriageRow({
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
    <div className={triageStyles.triageRow}>
      <label className={triageStyles.triageField}>
        <span className={triageStyles.fieldLabel}>Status</span>
        <select
          className={triageStyles.select}
          value={status}
          onChange={(e) => setStatus(e.target.value as RepoFeedbackStatus)}
        >
          {REPO_FEEDBACK_STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </label>
      <label className={`${triageStyles.triageField} ${triageStyles.triageFieldWide}`}>
        <span className={triageStyles.fieldLabel}>Resolution URL</span>
        <input
          type="url"
          className={triageStyles.textInput}
          placeholder="https://..."
          value={resolutionUrl}
          onChange={(e) => setResolutionUrl(e.target.value)}
        />
      </label>
      <button type="button" className={triageStyles.saveBtn} disabled={saving} onClick={handleSave}>
        {saving ? 'Saving...' : 'Save'}
      </button>
      {error && <p className={triageStyles.saveError} role="alert">{error}</p>}
    </div>
  );
}

function hasDetails(details: RepoFeedbackItem['details']): details is RepoFeedbackDetails {
  return Boolean(details && Object.keys(details).length > 0);
}

function ResolutionLink({ url }: { url: string }) {
  return (
    <p className={cardStyles.resolutionLink}>
      <a href={url} target="_blank" rel="noreferrer">{url}</a>
    </p>
  );
}

function uniqueValues(
  items: RepoFeedbackItem[],
  pick: (item: RepoFeedbackItem) => string | null | undefined,
): string[] {
  const set = new Set<string>();
  items.forEach((item) => {
    const value = pick(item);
    if (value) set.add(value);
  });
  return Array.from(set).sort();
}

function formatLabel(value: string): string {
  return value.replace(/_/g, ' ');
}
