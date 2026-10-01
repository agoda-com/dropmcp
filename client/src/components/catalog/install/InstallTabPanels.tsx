import CopyableSnippet from './CopyableSnippet';
import styles from './InstallPanel.module.css';

export default function InstallTabPanels({ activeTab, serverKey, mcpUrl }: { activeTab: string; serverKey: string; mcpUrl: string }) {
  return (
    <>
      <ClientTabPanel id="cursor" activeTab={activeTab}>
        <CopyableSnippet id="snippet-cursor" text={`{\n  "mcpServers": {\n    "${serverKey}": {\n      "url": "${mcpUrl}"\n    }\n  }\n}`} />
      </ClientTabPanel>

      <ClientTabPanel id="claude" activeTab={activeTab}>
        <CopyableSnippet id="snippet-claude" text={`claude mcp add ${serverKey} --transport http ${mcpUrl}`} />
      </ClientTabPanel>

      <ClientTabPanel id="desktop" activeTab={activeTab}>
        <p className={styles.desktopHint}>
          In Claude Desktop, go to <strong>Customize → Connectors → +</strong> (top right) then fill in:
        </p>
        <div className={styles.desktopFields}>
          <div className={styles.desktopField}>
            <label className={styles.desktopLabel}>Name</label>
            <CopyableSnippet id="snippet-desktop-name" text={serverKey} />
          </div>
          <div className={styles.desktopField}>
            <label className={styles.desktopLabel}>Remote MCP server URL</label>
            <CopyableSnippet id="snippet-desktop-url" text={mcpUrl} />
          </div>
        </div>
      </ClientTabPanel>

      <ClientTabPanel id="copilot" activeTab={activeTab}>
        <CopyableSnippet id="snippet-copilot" text={`{\n  "mcp": {\n    "servers": {\n      "${serverKey}": {\n        "type": "http",\n        "url": "${mcpUrl}"\n      }\n    }\n  }\n}`} />
      </ClientTabPanel>

      <ClientTabPanel id="codex" activeTab={activeTab}>
        <CopyableSnippet id="snippet-codex" text={`codex --mcp-server-url ${mcpUrl}`} />
      </ClientTabPanel>

      <ClientTabPanel id="gemini" activeTab={activeTab}>
        <CopyableSnippet id="snippet-gemini" text={`{\n  "mcpServers": {\n    "${serverKey}": {\n      "uri": "${mcpUrl}"\n    }\n  }\n}`} />
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
