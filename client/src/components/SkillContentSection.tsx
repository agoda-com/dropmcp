import { lazy, Suspense, useDeferredValue } from 'react';
import LoadingSpinner from './LoadingSpinner';
import styles from './SkillContentSection.module.css';

const Markdown = lazy(() => import('./Markdown'));

interface SkillContentSectionProps {
  markdown: string;
}

export default function SkillContentSection({ markdown }: SkillContentSectionProps) {
  const deferredMarkdown = useDeferredValue(markdown);
  const isRendering = deferredMarkdown !== markdown;

  return (
    <section className={styles.section} aria-labelledby="skill-instructions-heading">
      <h2 id="skill-instructions-heading">Instructions</h2>
      {isRendering ? (
        <LoadingSpinner label="Loading instructions…" />
      ) : (
        <Suspense fallback={<LoadingSpinner label="Loading instructions…" />}>
          <Markdown>{deferredMarkdown}</Markdown>
        </Suspense>
      )}
    </section>
  );
}
