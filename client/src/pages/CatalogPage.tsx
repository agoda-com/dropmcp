import { useState, useMemo } from 'react';
import { useCatalog } from '../context/CatalogContext';
import InstallPanel from '../components/InstallPanel';
import SearchToolbar from '../components/SearchToolbar';
import CatalogGrid, { SkeletonGrid, EmptyState, ErrorState } from '../components/CatalogGrid';
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
      {loading && <SkeletonGrid />}
      {error && <ErrorState message={error} />}
      {!loading && !error && filtered.length === 0 && items.length > 0 && <EmptyState />}
      {!loading && !error && items.length === 0 && (
        <div className={styles.emptyWrap}>
          <h2>Catalog is empty</h2>
          <p>No skills or prompts are available yet.</p>
        </div>
      )}
      {!loading && !error && filtered.length > 0 && <CatalogGrid items={filtered} />}
    </main>
  );
}
