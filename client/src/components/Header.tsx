import { useCatalog } from '../context/CatalogContext';
import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';
import MemoryNavLink from './memory/MemoryNavLink';
import styles from './Header.module.css';

export default function Header() {
  const { server, feedbackEnabled, repoFeedbackEnabled, benchmarksEnabled, me } =
    useCatalog();
  const links = [
    feedbackEnabled ? <Link key="feedback" to="/feedback">Feedback</Link> : null,
    repoFeedbackEnabled
      ? <Link key="repo-feedback" to="/repo-feedback">Repo feedback</Link>
      : null,
    benchmarksEnabled && me.authenticated
      ? <Link key="benchmarks" to="/benchmarks">Benchmarks</Link>
      : null,
  ].filter(Boolean);

  return (
    <header className={styles.banner}>
      <div className={styles.inner}>
        {server.icon_url && (
          <img src={server.icon_url} alt="" className={styles.icon} />
        )}
        <div>
          <h1>{server.name}</h1>
          <p>
            Browse skills and prompts for AI agents
            {links.length > 0 && <> · {joinLinks(links)}</>}
            <MemoryNavLink />
          </p>
        </div>
      </div>
    </header>
  );
}

function joinLinks(links: ReactNode[]) {
  return links.flatMap((link, index) =>
    index === 0 ? [link] : [' · ', link],
  );
}
