import type { CatalogItem } from '../api/catalog';
import CatalogGrid from './CatalogGrid';
import CatalogNoMatches from './CatalogNoMatches';
import CatalogSkeletonGrid from './CatalogSkeletonGrid';
import ErrorState from './ErrorState';
import styles from './CatalogResults.module.css';

export default function CatalogResults({
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
  if (loading) return <CatalogSkeletonGrid />;
  if (error) return <ErrorState message={error} />;
  if (items.length === 0) return <EmptyCatalog />;
  if (filtered.length === 0) return <CatalogNoMatches />;
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
