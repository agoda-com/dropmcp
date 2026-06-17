import { useCatalog } from '../context/CatalogContext';
import { Link } from 'react-router-dom';
import styles from './Header.module.css';

export default function Header() {
  const { server } = useCatalog();

  return (
    <header className={styles.banner}>
      <div className={styles.inner}>
        {server.icon_url && (
          <img src={server.icon_url} alt="" className={styles.icon} />
        )}
        <div>
          <h1>{server.name}</h1>
          <p>
            Browse skills and prompts for AI agents ·{' '}
            <Link to="/feedback">Feedback</Link>
          </p>
        </div>
      </div>
    </header>
  );
}
