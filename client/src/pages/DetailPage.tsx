import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchCatalogItem, type CatalogItem } from '../api/catalog';
import ArgumentsSection from '../components/ArgumentsSection';
import ExamplesSection from '../components/ExamplesSection';
import ItemHeader from '../components/ItemHeader';
import ItemHero from '../components/ItemHero';
import ScreenshotsSection from '../components/ScreenshotsSection';
import SkillContentSection from '../components/SkillContentSection';
import ResourcesSection from '../components/ResourcesSection';
import TelemetryPanel from '../components/TelemetryPanel';
import ErrorState from '../components/ErrorState';
import { formatName } from '../utils/format';
import styles from './DetailPage.module.css';

export default function DetailPage() {
  const { type, name } = useParams<{ type: string; name: string }>();
  const [item, setItem] = useState<CatalogItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!type || !name) return;
    setLoading(true);
    setError(null);
    fetchCatalogItem(type, name)
      .then(setItem)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [type, name]);

  if (loading) {
    return (
      <main className={styles.main}>
        <div className={styles.loading}>
          <div className={styles.spinner} />
        </div>
      </main>
    );
  }

  if (error || !item) {
    return (
      <main className={styles.main}>
        <Link to="/" className={styles.back}>← Back to catalog</Link>
        <ErrorState message={error || 'Item not found'} />
      </main>
    );
  }

  const args = Array.isArray(item.arguments) ? item.arguments : [];
  const shots = Array.isArray(item.screenshots) ? item.screenshots : [];
  const examples = Array.isArray(item.examples) ? item.examples : [];
  const heroUrl = item.hero_url || item.thumbnail_url;

  return (
    <main className={styles.main}>
      <Link to="/" className={styles.back}>← Back to catalog</Link>

      <ItemHero heroUrl={heroUrl} altText={formatName(item.name)} />

      <div className={styles.content}>
        <ItemHeader item={item} />

        {args.length > 0 && item.type === 'prompt' && (
          <ArgumentsSection args={args} />
        )}

        {shots.length > 0 && (
          <ScreenshotsSection urls={shots} />
        )}

        {examples.length > 0 && (
          <ExamplesSection examples={examples} />
        )}

        {item.type === 'skill' && item.content_markdown && (
          <SkillContentSection markdown={item.content_markdown} />
        )}
        {item.type === 'skill' && (item.resources?.length ?? 0) > 0 && (
          <ResourcesSection resources={item.resources!} />
        )}

        <TelemetryPanel itemName={item.name} />
      </div>
    </main>
  );
}
