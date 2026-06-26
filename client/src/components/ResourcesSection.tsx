import { useState } from 'react';
import type { SkillResource } from '../api/catalog';
import ResourceModal from './ResourceModal';
import styles from './ResourcesSection.module.css';

interface ResourcesSectionProps {
  resources: SkillResource[];
}

export default function ResourcesSection({ resources }: ResourcesSectionProps) {
  const [activeResource, setActiveResource] = useState<SkillResource | null>(null);

  return (
    <section className={styles.section} aria-labelledby="skill-resources-heading">
      <h2 id="skill-resources-heading">Resources</h2>
      <ul className={styles.list}>
        {resources.map((resource) => (
          <li key={resource.path}>
            <button
              type="button"
              className={styles.link}
              onClick={() => setActiveResource(resource)}
            >
              {resource.path}
            </button>
          </li>
        ))}
      </ul>

      {activeResource && (
        <ResourceModal
          resource={activeResource}
          onClose={() => setActiveResource(null)}
        />
      )}
    </section>
  );
}
