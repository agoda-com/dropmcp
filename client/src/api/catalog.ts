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

export interface TelemetryResult {
  passed: boolean;
  score: number;
  threshold: number;
  display_score: string;
  display_threshold: string;
  display_duration: string;
  display_date: string;
  reasoning: string;
  error: string | null;
  worker_model: string;
  pipeline_id: string;
  short_sha: string;
}

export interface SkillTelemetryResult extends TelemetryResult {
  test_name: string;
}

export interface TelemetryResponse {
  project: string;
  skill_name: string;
  results: SkillTelemetryResult[];
}

export interface TelemetryAllResponse {
  project: string;
  results: Record<string, (TelemetryResult & { test_name: string })[]>;
}

export async function fetchTelemetry(skillName: string): Promise<TelemetryResponse> {
  const res = await fetch(`/api/telemetry/${skillName}`);
  if (!res.ok) {
    return { project: '', skill_name: skillName, results: [] };
  }
  return res.json();
}

export async function fetchAllTelemetry(): Promise<TelemetryAllResponse> {
  const res = await fetch('/api/telemetry');
  if (!res.ok) {
    return { project: '', results: {} };
  }
  return res.json();
}
