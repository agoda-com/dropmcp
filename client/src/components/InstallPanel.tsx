import { useMemo, useState } from 'react';
import { useCatalog } from '../context/CatalogContext';
import InstallTabList from './InstallTabList';
import InstallTabPanels from './InstallTabPanels';
import styles from './InstallPanel.module.css';

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'mcp-server';
}

export default function InstallPanel() {
  const { server } = useCatalog();
  const [open, setOpen] = useState(true);
  const [activeTab, setActiveTab] = useState('cursor');

  const serverKey = useMemo(() => slugify(server.name), [server.name]);
  const mcpUrl = useMemo(() => `${window.location.origin}/mcp`, []);

  return (
    <section className={styles.panel} data-open={open} aria-label="Installation instructions">
      <PanelToggle open={open} onToggle={() => setOpen(!open)} />

      <div className={styles.body}>
        <div className={styles.bodyInner}>
          <div className={styles.content}>
            <InstallTabList activeTab={activeTab} onTabChange={setActiveTab} />
            <InstallTabPanels activeTab={activeTab} serverKey={serverKey} mcpUrl={mcpUrl} />
          </div>
        </div>
      </div>
    </section>
  );
}

function PanelToggle({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      className={styles.toggle}
      onClick={onToggle}
      aria-expanded={open}
    >
      <span>Get Started — Install</span>
      <svg className={styles.chevron} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path d="M6 9l6 6 6-6" />
      </svg>
    </button>
  );
}
