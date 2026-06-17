import { useState, useMemo } from 'react';
import { useCatalog } from '../context/CatalogContext';
import InstallPanel from '../components/InstallPanel';
import SearchToolbar from '../components/SearchToolbar';
import CatalogGrid, { SkeletonGrid, EmptyState, ErrorState } from '../components/CatalogGrid';
import type { CatalogItem } from '../api/catalog';
import styles from './CatalogPage.module.css';

export default function CatalogPage() {
  const { items, loading, error } = useCatalog();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  const categories = useMemo(() => {
    const set = new Set<string>();
    items.forEach((i) => { if (i.category) set.add(i.category); });
    return Array.from(set).sort();
  }, [items]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((item) => {
      if (typeFilter !== 'all' && item.type !== typeFilter) return false;
      if (categoryFilter && item.category !== categoryFilter) return false;
      if (!q) return true;
      return (
        item.name.toLowerCase().includes(q) ||
        (item.description || '').toLowerCase().includes(q)
      );
    });
  }, [items, search, typeFilter, categoryFilter]);

  return (
    <main className={styles.main}>
      <InstallPanel />

      <SearchToolbar
        search={search}
        onSearchChange={setSearch}
        typeFilter={typeFilter}
        onTypeChange={setTypeFilter}
        categories={categories}
        categoryFilter={categoryFilter}
        onCategoryChange={setCategoryFilter}
      />

      <CatalogContent
        loading={loading}
        error={error}
        items={items}
        filtered={filtered}
      />
    </main>
  );
}

function CatalogContent({
  loading,
  error,
  items,
  filtered,
}: {
  loading: boolean;
  error: string | null;
  items: CatalogItem[];
  filtered: CatalogItem[];
}) {
  if (loading) return <SkeletonGrid />;
  if (error) return <ErrorState message={error} />;
  if (items.length === 0) return <EmptyCatalog />;
  if (filtered.length === 0) return <EmptyState />;
  return <CatalogGrid items={filtered} />;
}

function EmptyCatalog() {
  return (
    <div className={styles.emptyWrap}>
      <h2>Catalog is empty</h2>
      <p>No skills or prompts are available yet.</p>
    </div>
  );
}
