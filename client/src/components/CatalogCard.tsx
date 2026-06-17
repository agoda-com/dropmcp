import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import type { CatalogItem } from '../api/catalog';
import styles from './CatalogCard.module.css';

function formatName(kebab: string): string {
  return kebab
    .split('-')
    .map((w) => (w.length ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : ''))
    .join(' ');
}

export default function CatalogCard({ item }: { item: CatalogItem }) {
  const [imgFailed, setImgFailed] = useState(false);
  const type = item.type || 'skill';
  const argCount = Array.isArray(item.arguments) ? item.arguments.length : 0;
  const detailPath = `/${type}/${item.name}`;

  const handleImgError = useCallback(() => setImgFailed(true), []);

  return (
    <Link to={detailPath} className={styles.card}>
      <div className={`${styles.thumb} ${!item.thumbnail_url || imgFailed ? styles.fallback : ''}`}>
        {item.thumbnail_url && !imgFailed && (
          <img src={item.thumbnail_url} alt="" loading="lazy" onError={handleImgError} />
        )}
        <div className={styles.thumbFallback} aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
        </div>
      </div>
      <div className={styles.body}>
        <div className={styles.badges}>
          <span className={`${styles.badge} ${type === 'prompt' ? styles.badgePrompt : styles.badgeSkill}`}>
            {type === 'prompt' ? 'Prompt' : 'Skill'}
          </span>
          {item.category && (
            <span className={`${styles.badge} ${styles.badgeCat}`}>{formatName(item.category)}</span>
          )}
        </div>
        <h3 className={styles.title}>{formatName(item.name)}</h3>
        <p className={styles.desc}>{item.description}</p>
        {type === 'prompt' && (
          <div className={styles.meta}>
            <span className={styles.chipArgs}>{argCount} arg{argCount === 1 ? '' : 's'}</span>
          </div>
        )}
      </div>
    </Link>
  );
}
