import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchCatalogItem, type CatalogItem } from '../api/catalog';
import ScreenshotGallery from '../components/ScreenshotGallery';
import SkillContentSection from '../components/SkillContentSection';
import ResourcesSection from '../components/ResourcesSection';
import TelemetryPanel from '../components/TelemetryPanel';
import { ErrorState } from '../components/CatalogGrid';
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
        <ItemMetadata item={item} />

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

function ItemHero({ heroUrl, altText }: { heroUrl: string | null | undefined; altText: string }) {
  if (heroUrl) {
    return (
      <div className={styles.hero}>
        <img src={heroUrl} alt={altText} />
      </div>
    );
  }
  return <div className={styles.heroPlaceholder} />;
}

function ItemMetadata({ item }: { item: CatalogItem }) {
  return (
    <>
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
    </>
  );
}

type Argument = { name: string; required: boolean; description?: string };

function ArgumentsSection({ args }: { args: Argument[] }) {
  return (
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
  );
}

function ScreenshotsSection({ urls }: { urls: string[] }) {
  return (
    <section className={styles.section}>
      <h2>Screenshots</h2>
      <ScreenshotGallery urls={urls} />
    </section>
  );
}

function ExamplesSection({ examples }: { examples: unknown[] }) {
  return (
    <section className={styles.section}>
      <h2>Examples</h2>
      <ul className={styles.examplesList}>
        {examples.map((ex, i) => (
          <li key={i}>{String(ex)}</li>
        ))}
      </ul>
    </section>
  );
}
