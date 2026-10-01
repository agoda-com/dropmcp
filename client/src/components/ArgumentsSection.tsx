import DetailSection from './DetailSection';
import styles from './ArgumentsSection.module.css';

type Argument = { name: string; required: boolean; description?: string };

export default function ArgumentsSection({ args }: { args: Argument[] }) {
  return (
    <DetailSection title="Arguments">
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
    </DetailSection>
  );
}
