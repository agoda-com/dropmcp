import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  fetchRepoFeedback,
  type RepoFeedbackCategory,
  type RepoFeedbackItem,
  type RepoFeedbackSort,
  type RepoFeedbackStatus,
} from '../api/repoFeedback';
import FeedbackHeader from '../components/FeedbackHeader';
import RepoFeedbackList from '../components/RepoFeedbackList';
import RepoFeedbackToolbar from '../components/RepoFeedbackToolbar';
import pageStyles from './FeedbackPage.module.css';

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
  const [sortMode, setSortMode] = useState<RepoFeedbackSort>('priority');

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
