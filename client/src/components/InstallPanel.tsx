import { useMemo, useState, useCallback } from 'react';
import { useCatalog } from '../context/CatalogContext';
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
            <ClientTabList activeTab={activeTab} onTabChange={setActiveTab} />
            <ClientTabPanels activeTab={activeTab} serverKey={serverKey} mcpUrl={mcpUrl} />
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

const CLIENT_TABS = ['cursor', 'claude', 'desktop', 'copilot', 'codex', 'gemini'] as const;
type ClientTab = typeof CLIENT_TABS[number];

const TAB_LABELS: Record<ClientTab, string> = {
  cursor: 'Cursor',
  claude: 'Claude Code',
  desktop: 'Claude Desktop',
  copilot: 'VS Code Copilot',
  codex: 'Codex CLI',
  gemini: 'Google AI Studio',
};

function ClientTabList({ activeTab, onTabChange }: { activeTab: string; onTabChange: (tab: string) => void }) {
  return (
    <div className={styles.tablist} role="tablist" aria-label="Client">
      {CLIENT_TABS.map((tab) => (
        <button
          key={tab}
          type="button"
          className={styles.tab}
          role="tab"
          aria-selected={activeTab === tab}
          onClick={() => onTabChange(tab)}
        >
          {TAB_LABELS[tab]}
        </button>
      ))}
    </div>
  );
}

function ClientTabPanels({ activeTab, serverKey, mcpUrl }: { activeTab: string; serverKey: string; mcpUrl: string }) {
  return (
    <>
      <ClientTabPanel id="cursor" activeTab={activeTab}>
        <Snippet id="snippet-cursor" text={`{\n  "mcpServers": {\n    "${serverKey}": {\n      "url": "${mcpUrl}"\n    }\n  }\n}`} />
      </ClientTabPanel>

      <ClientTabPanel id="claude" activeTab={activeTab}>
        <Snippet id="snippet-claude" text={`claude mcp add ${serverKey} --transport http ${mcpUrl}`} />
      </ClientTabPanel>

      <ClientTabPanel id="desktop" activeTab={activeTab}>
        <p className={styles.desktopHint}>
          In Claude Desktop, go to <strong>Customize → Connectors → +</strong> (top right) then fill in:
        </p>
        <div className={styles.desktopFields}>
          <div className={styles.desktopField}>
            <label className={styles.desktopLabel}>Name</label>
            <Snippet id="snippet-desktop-name" text={serverKey} />
          </div>
          <div className={styles.desktopField}>
            <label className={styles.desktopLabel}>Remote MCP server URL</label>
            <Snippet id="snippet-desktop-url" text={mcpUrl} />
          </div>
        </div>
      </ClientTabPanel>

      <ClientTabPanel id="copilot" activeTab={activeTab}>
        <Snippet id="snippet-copilot" text={`{\n  "mcp": {\n    "servers": {\n      "${serverKey}": {\n        "type": "http",\n        "url": "${mcpUrl}"\n      }\n    }\n  }\n}`} />
      </ClientTabPanel>

      <ClientTabPanel id="codex" activeTab={activeTab}>
        <Snippet id="snippet-codex" text={`codex --mcp-server-url ${mcpUrl}`} />
      </ClientTabPanel>

      <ClientTabPanel id="gemini" activeTab={activeTab}>
        <Snippet id="snippet-gemini" text={`{\n  "mcpServers": {\n    "${serverKey}": {\n      "uri": "${mcpUrl}"\n    }\n  }\n}`} />
      </ClientTabPanel>
    </>
  );
}

function ClientTabPanel({ id, activeTab, children }: { id: string; activeTab: string; children: React.ReactNode }) {
  return (
    <div
      className={styles.tabPanel}
      role="tabpanel"
      aria-hidden={activeTab !== id}
      hidden={activeTab !== id}
    >
      {children}
    </div>
  );
}

function Snippet({ id, text }: { id: string; text: string }) {
  return (
    <div className={styles.snippetRow}>
      <div className={styles.snippetWrap}>
        <pre className={styles.snippet} id={id}>{text}</pre>
      </div>
      <CopyButton targetId={id} />
    </div>
  );
}

function CopyButton({ targetId }: { targetId: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    const el = document.getElementById(targetId);
    const text = el?.textContent ?? '';
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [targetId]);

  return (
    <button
      type="button"
      className={`${styles.btnCopy} ${copied ? styles.copied : ''}`}
      onClick={handleCopy}
    >
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}
