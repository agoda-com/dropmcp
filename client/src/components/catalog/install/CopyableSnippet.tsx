import { useCallback, useState } from 'react';
import styles from './InstallPanel.module.css';

export default function CopyableSnippet({ id, text }: { id: string; text: string }) {
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
