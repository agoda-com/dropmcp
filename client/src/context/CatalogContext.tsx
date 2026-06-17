import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import {
  fetchCatalog,
  type CatalogItem,
  type CatalogServer,
} from '../api/catalog';

interface CatalogState {
  items: CatalogItem[];
  server: CatalogServer;
  loading: boolean;
  error: string | null;
}

const defaultServer: CatalogServer = {
  name: 'Catalog',
  website_url: null,
  icon_url: null,
};

const CatalogContext = createContext<CatalogState>({
  items: [],
  server: defaultServer,
  loading: true,
  error: null,
});

export function CatalogProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [server, setServer] = useState<CatalogServer>(defaultServer);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCatalog()
      .then((data) => {
        setItems(data.items);
        setServer(data.server);
        if (data.server.name) {
          document.title = data.server.name;
        }
        if (data.server.icon_url) {
          let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
          if (!link) {
            link = document.createElement('link');
            link.rel = 'icon';
            link.type = 'image/svg+xml';
            document.head.appendChild(link);
          }
          link.href = data.server.icon_url;
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <CatalogContext.Provider value={{ items, server, loading, error }}>
      {children}
    </CatalogContext.Provider>
  );
}

export function useCatalog() {
  return useContext(CatalogContext);
}
