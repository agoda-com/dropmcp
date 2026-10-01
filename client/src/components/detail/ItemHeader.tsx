import type { CatalogItem } from '../../api/catalog';
import { formatName } from '../../utils/format';
import styles from './ItemHeader.module.css';

export default function ItemHeader({ item }: { item: CatalogItem }) {
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
