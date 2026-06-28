import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchFeedback, type FeedbackItem, type FeedbackStatus, type FeedbackType } from '../api/feedback';
import FeedbackHeader from '../components/FeedbackHeader';
import FeedbackToolbar from '../components/FeedbackToolbar';
import FeedbackList from '../components/FeedbackList';
import styles from './FeedbackPage.module.css';

export default function FeedbackPage() {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<FeedbackStatus | 'all'>('all');
  const [typeFilter, setTypeFilter] = useState<FeedbackType | 'all'>('all');
  const [modelFilter, setModelFilter] = useState<string | null>(null);
  const [clientFilter, setClientFilter] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchFeedback({
        search: search.trim() || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter,
        feedback_type: typeFilter === 'all' ? undefined : typeFilter,
        model: modelFilter ?? undefined,
        client: clientFilter ?? undefined,
      });
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load feedback.');
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, typeFilter, modelFilter, clientFilter]);

  useEffect(() => {
    const timer = setTimeout(load, search ? 250 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  const models = useMemo(() => uniqueValues(items, (item) => item.model), [items]);
  const clients = useMemo(() => uniqueValues(items, (item) => item.client), [items]);

  return (
    <main className={styles.feedbackPage}>
      <FeedbackHeader />

      <FeedbackToolbar
        search={search}
        onSearchChange={setSearch}
        statusFilter={statusFilter}
        onStatusChange={setStatusFilter}
        typeFilter={typeFilter}
        onTypeChange={setTypeFilter}
        models={models}
        modelFilter={modelFilter}
        onModelChange={setModelFilter}
        clients={clients}
        clientFilter={clientFilter}
        onClientChange={setClientFilter}
      />

      <FeedbackList loading={loading} error={error} items={items} onItemUpdated={load} />
    </main>
  );
}

function uniqueValues(
  items: FeedbackItem[],
  pick: (item: FeedbackItem) => string | null | undefined,
): string[] {
  const set = new Set<string>();
  items.forEach((item) => {
    const value = pick(item);
    if (value) set.add(value);
  });
  return Array.from(set).sort();
}
