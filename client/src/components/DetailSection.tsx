import type { ReactNode } from 'react';
import styles from './DetailSection.module.css';

export default function DetailSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={styles.section}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}
