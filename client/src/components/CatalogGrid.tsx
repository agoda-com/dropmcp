import type { CatalogItem } from '../api/catalog';
import CatalogCard from './CatalogCard';
import styles from './CatalogGrid.module.css';

export default function CatalogGrid({ items }: { items: CatalogItem[] }) {
  return (
    <div className={styles.grid}>
      {items.map((item) => (
        <CatalogCard key={`${item.type}-${item.name}`} item={item} />
      ))}
    </div>
  );
}
