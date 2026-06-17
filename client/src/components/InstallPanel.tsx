import { useMemo, useState, useCallback } from 'react';
import { useCatalog } from '../context/CatalogContext';
import styles from './InstallPanel.module.css';

interface TabDef {
  id: string;
  label: string;
  content: React.ReactNode;
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'mcp-server';
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

export default function InstallPanel() {
  const { server } = useCatalog();
  const [open, setOpen] = useState(true);
  const [activeTab, setActiveTab] = useState('cursor');

  const serverKey = useMemo(() => slugify(server.name), [server.name]);
  const mcpUrl = useMemo(() => `${window.location.origin}/mcp`, []);

  const tabs: TabDef[] = useMemo(
    () => [
      {
        id: 'cursor',
        label: 'Cursor',
        content: (
          <Snippet
            id="snippet-cursor"
            text={`{
  "mcpServers": {
    "${serverKey}": {
      "url": "${mcpUrl}"
    }
  }
}`}
          />
        ),
      },
      {
        id: 'claude',
        label: 'Claude Code',
        content: (
          <Snippet
            id="snippet-claude"
            text={`claude mcp add ${serverKey} --transport http ${mcpUrl}`}
          />
        ),
      },
      {
        id: 'desktop',
        label: 'Claude Desktop',
        content: (
          <div>
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
          </div>
        ),
      },
      {
        id: 'copilot',
        label: 'VS Code Copilot',
        content: (
          <Snippet
            id="snippet-copilot"
            text={`{
  "mcp": {
    "servers": {
      "${serverKey}": {
        "type": "http",
        "url": "${mcpUrl}"
      }
    }
  }
}`}
          />
        ),
      },
      {
        id: 'codex',
        label: 'Codex CLI',
        content: (
          <Snippet id="snippet-codex" text={`codex --mcp-server-url ${mcpUrl}`} />
        ),
      },
      {
        id: 'gemini',
        label: 'Google AI Studio',
        content: (
          <Snippet
            id="snippet-gemini"
            text={`{
  "mcpServers": {
    "${serverKey}": {
      "uri": "${mcpUrl}"
    }
  }
}`}
          />
        ),
      },
    ],
    [mcpUrl, serverKey],
  );

  return (
    <section className={styles.panel} data-open={open} aria-label="Installation instructions">
      <button
        type="button"
        className={styles.toggle}
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span>Get Started — Install</span>
        <svg className={styles.chevron} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      <div className={styles.body}>
        <div className={styles.bodyInner}>
          <div className={styles.content}>
            <div className={styles.tablist} role="tablist" aria-label="Client">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  className={styles.tab}
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            {tabs.map((tab) => (
              <div
                key={tab.id}
                className={styles.tabPanel}
                role="tabpanel"
                aria-hidden={activeTab !== tab.id}
                hidden={activeTab !== tab.id}
              >
                {tab.content}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
