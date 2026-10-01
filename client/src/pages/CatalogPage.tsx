import { useState, useMemo } from 'react';
import { useCatalog } from '../context/CatalogContext';
import InstallPanel from '../components/InstallPanel';
import SearchToolbar from '../components/SearchToolbar';
import CatalogResults from '../components/CatalogResults';
import styles from './CatalogPage.module.css';

export default function CatalogPage() {
  const { items, loading, error } = useCatalog();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [groupFilter, setGroupFilter] = useState<string | null>(null);

  const categories = useMemo(() => {
    const set = new Set<string>();
    items.forEach((i) => { if (i.category) set.add(i.category); });
    return Array.from(set).sort();
  }, [items]);

  const groups = useMemo(() => {
    const set = new Set<string>();
    items.forEach((i) => { if (i.group) set.add(i.group); });
    return Array.from(set).sort();
  }, [items]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((item) => {
      if (typeFilter !== 'all' && item.type !== typeFilter) return false;
      if (categoryFilter && item.category !== categoryFilter) return false;
      if (groupFilter && item.group !== groupFilter) return false;
      if (!q) return true;
      return (
        item.name.toLowerCase().includes(q) ||
        (item.description || '').toLowerCase().includes(q)
      );
    });
  }, [items, search, typeFilter, categoryFilter, groupFilter]);

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
        groups={groups}
        groupFilter={groupFilter}
        onGroupChange={setGroupFilter}
        allItems={items}
      />

      <CatalogResults
        loading={loading}
        error={error}
        items={items}
        filtered={filtered}
      />
    </main>
  );
}
