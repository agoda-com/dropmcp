import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchCatalogItem, type CatalogItem } from '../api/catalog';
import ScreenshotGallery from '../components/ScreenshotGallery';
import { ErrorState } from '../components/CatalogGrid';
import styles from './DetailPage.module.css';

function formatName(kebab: string): string {
  return kebab
    .split('-')
    .map((w) => (w.length ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : ''))
    .join(' ');
}

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

      {heroUrl && (
        <div className={styles.hero}>
          <img src={heroUrl} alt={formatName(item.name)} />
        </div>
      )}
      {!heroUrl && <div className={styles.heroPlaceholder} />}

      <div className={styles.content}>
        <div className={styles.badges}>
          <span className={`${styles.badge} ${item.type === 'prompt' ? styles.badgePrompt : styles.badgeSkill}`}>
            {item.type === 'prompt' ? 'Prompt' : 'Skill'}
          </span>
          {item.category && (
            <span className={`${styles.badge} ${styles.badgeCat}`}>{formatName(item.category)}</span>
          )}
        </div>

        <h1 className={styles.title}>{formatName(item.name)}</h1>
        <p className={styles.desc}>{item.description}</p>

        {args.length > 0 && item.type === 'prompt' && (
          <section className={styles.section}>
            <h2>Arguments</h2>
            <ul className={styles.argList}>
              {args.map((a) => (
                <li key={a.name} className={styles.argItem}>
                  <span className={styles.argName}>{a.name}</span>
                  <span className={`${styles.reqBadge} ${a.required ? styles.required : styles.optional}`}>
                    {a.required ? 'Required' : 'Optional'}
                  </span>
                  {a.description && <span className={styles.argDesc}>{a.description}</span>}
                </li>
              ))}
            </ul>
          </section>
        )}

        {shots.length > 0 && (
          <section className={styles.section}>
            <h2>Screenshots</h2>
            <ScreenshotGallery urls={shots} />
          </section>
        )}

        {examples.length > 0 && (
          <section className={styles.section}>
            <h2>Examples</h2>
            <ul className={styles.examplesList}>
              {examples.map((ex, i) => (
                <li key={i}>{String(ex)}</li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </main>
  );
}
