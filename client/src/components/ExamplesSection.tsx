import DetailSection from './DetailSection';
import styles from './ExamplesSection.module.css';

export default function ExamplesSection({ examples }: { examples: unknown[] }) {
  return (
    <DetailSection title="Examples">
      <ul className={styles.examplesList}>
        {examples.map((ex, i) => (
          <li key={i}>{String(ex)}</li>
        ))}
      </ul>
    </DetailSection>
  );
}
