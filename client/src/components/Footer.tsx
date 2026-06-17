import { useCatalog } from '../context/CatalogContext';
import styles from './Footer.module.css';

export default function Footer() {
  const { server } = useCatalog();

  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <div className={styles.links}>
          {server.website_url && (
            <a href={server.website_url} target="_blank" rel="noopener noreferrer">
              Website
            </a>
          )}
          <a href="https://gofastmcp.com" target="_blank" rel="noopener noreferrer">
            Powered by FastMCP
          </a>
        </div>
        <span>{server.name}</span>
      </div>
    </footer>
  );
}
