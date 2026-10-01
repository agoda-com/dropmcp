import styles from './InstallPanel.module.css';

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

export default function InstallTabList({ activeTab, onTabChange }: { activeTab: string; onTabChange: (tab: string) => void }) {
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
