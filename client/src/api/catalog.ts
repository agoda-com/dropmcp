export interface CatalogItem {
  name: string;
  type: 'skill' | 'prompt';
  category: string;
  description: string;
  arguments: { name: string; required: boolean; description: string }[];
  has_hero: boolean;
  has_thumbnail: boolean;
  screenshot_count: number;
  example_count: number;
  thumbnail_url: string | null;
  hero_url: string | null;
  screenshots: string[];
  examples: string[];
}

export interface CatalogServer {
  name: string;
  website_url: string | null;
  icon_url: string | null;
}

interface CatalogResponse {
  items: CatalogItem[];
  server: CatalogServer;
}

export async function fetchCatalog(): Promise<CatalogResponse> {
  const res = await fetch('/catalog');
  if (!res.ok) throw new Error(`Could not load catalog (${res.status}).`);
  const data: CatalogResponse = await res.json();
  return {
    items: Array.isArray(data.items) ? data.items : [],
    server: data.server ?? { name: 'Catalog', website_url: null, icon_url: null },
  };
}

export async function fetchCatalogItem(
  type: string,
  name: string,
): Promise<CatalogItem> {
  const res = await fetch(`/catalog/${type}/${name}`);
  if (!res.ok) throw new Error(`Item not found (${res.status}).`);
  return res.json();
}
