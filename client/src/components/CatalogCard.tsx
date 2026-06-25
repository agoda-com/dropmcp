import { useCallback, useState, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import type { CatalogItem } from '../api/catalog';
import { subscribeItem, unsubscribeItem } from '../api/subscriptions';
import { useCatalog } from '../context/CatalogContext';
import { formatName } from '../utils/format';
import styles from './CatalogCard.module.css';

export default function CatalogCard({ item }: { item: CatalogItem }) {
  const type = item.type || 'skill';
  const detailPath = `/${type}/${item.name}`;
  const {
    subscriptionControlsEnabled,
    updateItemSubscription,
  } = useCatalog();

  const handleSubscriptionToggle = async (
    event: MouseEvent<HTMLInputElement>,
  ) => {
    event.preventDefault();
    event.stopPropagation();
    const next = !item.subscribed;
    updateItemSubscription(type, item.name, next);
    try {
      if (next) {
        await subscribeItem(type, item.name);
      } else {
        await unsubscribeItem(type, item.name);
      }
    } catch {
      updateItemSubscription(type, item.name, !next);
    }
  };

  return (
    <div className={styles.cardWrap}>
      <Link to={detailPath} className={styles.card}>
        <CardThumbnail thumbnailUrl={item.thumbnail_url} />
        <CardBody item={item} type={type} />
      </Link>
      {subscriptionControlsEnabled && (
        <label
          className={styles.subscribeControl}
          onClick={(e) => e.stopPropagation()}
        >
          <input
            type="checkbox"
            checked={Boolean(item.subscribed)}
            aria-label={`Subscribe to ${item.name}`}
            onChange={() => {}}
            onClick={handleSubscriptionToggle}
          />
        </label>
      )}
    </div>
  );
}

function CardThumbnail({ thumbnailUrl }: { thumbnailUrl: string | null | undefined }) {
  const [imgFailed, setImgFailed] = useState(false);
  const handleImgError = useCallback(() => setImgFailed(true), []);
  const showFallback = !thumbnailUrl || imgFailed;

  return (
    <div className={`${styles.thumb} ${showFallback ? styles.fallback : ''}`}>
      {thumbnailUrl && !imgFailed && (
        <img src={thumbnailUrl} alt="" loading="lazy" onError={handleImgError} />
      )}
      <div className={styles.thumbFallback} aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5M2 12l10 5 10-5" />
        </svg>
      </div>
    </div>
  );
}

function CardBody({ item, type }: { item: CatalogItem; type: string }) {
  const argCount = Array.isArray(item.arguments) ? item.arguments.length : 0;

  return (
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
  );
}
