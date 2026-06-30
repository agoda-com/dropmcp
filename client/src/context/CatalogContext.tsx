import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import {
  fetchCatalog,
  type CatalogItem,
  type CatalogServer,
  type CurrentUserIdentity,
} from '../api/catalog';

interface CatalogState {
  items: CatalogItem[];
  server: CatalogServer;
  loading: boolean;
  error: string | null;
  subscriptionsEnabled: boolean;
  user: string | null;
  me: CurrentUserIdentity;
  subscriptionControlsEnabled: boolean;
  subscribedGroups: string[];
  updateItemSubscription: (
    type: 'skill' | 'prompt',
    name: string,
    subscribed: boolean,
  ) => void;
  updateGroupSubscriptions: (
    group: string,
    members: CatalogItem[],
    subscribed: boolean,
  ) => void;
}

const defaultServer: CatalogServer = {
  name: 'Catalog',
  website_url: null,
  icon_url: null,
};

const anonymousUser: CurrentUserIdentity = {
  email: null,
  authenticated: false,
};

const CatalogContext = createContext<CatalogState>({
  items: [],
  server: defaultServer,
  loading: true,
  error: null,
  subscriptionsEnabled: false,
  user: null,
  me: anonymousUser,
  subscriptionControlsEnabled: false,
  subscribedGroups: [],
  updateItemSubscription: () => {},
  updateGroupSubscriptions: () => {},
});

export function CatalogProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [server, setServer] = useState<CatalogServer>(defaultServer);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [subscriptionsEnabled, setSubscriptionsEnabled] = useState(false);
  const [user, setUser] = useState<string | null>(null);
  const [me, setMe] = useState<CurrentUserIdentity>(anonymousUser);
  const [subscribedGroups, setSubscribedGroups] = useState<string[]>([]);

  useEffect(() => {
    fetchCatalog()
      .then((data) => {
        setItems(data.items);
        setServer(data.server);
        setSubscriptionsEnabled(data.subscriptionsEnabled);
        setUser(data.user);
        setMe(data.me);
        setSubscribedGroups(data.subscribedGroups);
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

  const updateItemSubscription = useCallback(
    (type: 'skill' | 'prompt', name: string, subscribed: boolean) => {
      setItems((prev) =>
        prev.map((item) =>
          item.type === type && item.name === name
            ? {
                ...item,
                subscribed,
                subscription_state: subscribed
                  ? 'direct'
                  : item.group && subscribedGroups.includes(item.group)
                    ? 'excluded'
                    : 'none',
              }
            : item,
        ),
      );
    },
    [subscribedGroups],
  );

  const updateGroupSubscriptions = useCallback(
    (group: string, members: CatalogItem[], subscribed: boolean) => {
      const memberKeys = new Set(
        members.filter((m) => m.group === group).map((m) => `${m.type}:${m.name}`),
      );
      setSubscribedGroups((prev) =>
        subscribed
          ? [...new Set([...prev, group])]
          : prev.filter((g) => g !== group),
      );
      setItems((prev) =>
        prev.map((item) =>
          memberKeys.has(`${item.type}:${item.name}`)
            ? applyGroupSubscriptionState(item, subscribed)
            : item,
        ),
      );
    },
    [],
  );

  const subscriptionControlsEnabled = subscriptionsEnabled && user !== null;

  return (
    <CatalogContext.Provider
      value={{
        items,
        server,
        loading,
        error,
        subscriptionsEnabled,
        user,
        me,
        subscriptionControlsEnabled,
        subscribedGroups,
        updateItemSubscription,
        updateGroupSubscriptions,
      }}
    >
      {children}
    </CatalogContext.Provider>
  );
}

export function useCatalog() {
  return useContext(CatalogContext);
}

function applyGroupSubscriptionState(
  item: CatalogItem,
  groupSubscribed: boolean,
): CatalogItem {
  if (groupSubscribed) {
    if (item.subscription_state === 'direct') {
      return item;
    }
    return {
      ...item,
      subscribed: true,
      subscription_state: 'group',
    };
  }

  if (item.subscription_state === 'direct') {
    return item;
  }
  return {
    ...item,
    subscribed: false,
    subscription_state: 'none',
  };
}
