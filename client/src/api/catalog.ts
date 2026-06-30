export interface SkillResource {
  path: string;
  name: string;
  url: string;
  mime_type: string;
}

export interface CatalogItem {
  name: string;
  type: 'skill' | 'prompt';
  category: string;
  group?: string | null;
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
  subscribed?: boolean;
  subscription_state?: 'none' | 'direct' | 'group' | 'excluded';
  content_markdown?: string | null;
  resources?: SkillResource[];
}

export interface CatalogServer {
  name: string;
  website_url: string | null;
  icon_url: string | null;
}

export interface CurrentUserIdentity {
  email: string | null;
  authenticated: boolean;
}

interface CatalogResponse {
  items: CatalogItem[];
  server: CatalogServer;
  me?: CurrentUserIdentity;
  subscriptions_enabled?: boolean;
  user?: string | null;
  subscribed_groups?: string[];
  available_groups?: string[];
}

export async function fetchCatalog(): Promise<{
  items: CatalogItem[];
  server: CatalogServer;
  subscriptionsEnabled: boolean;
  user: string | null;
  me: CurrentUserIdentity;
  subscribedGroups: string[];
  availableGroups: string[];
}> {
  const res = await fetch('/catalog');
  if (!res.ok) throw new Error(`Could not load catalog (${res.status}).`);
  const data: CatalogResponse = await res.json();
  const me = normalizeIdentity(data.me, data.user);
  return {
    items: Array.isArray(data.items) ? data.items : [],
    server: data.server ?? { name: 'Catalog', website_url: null, icon_url: null },
    subscriptionsEnabled: Boolean(data.subscriptions_enabled),
    user: me.email,
    me,
    subscribedGroups: Array.isArray(data.subscribed_groups)
      ? data.subscribed_groups
      : [],
    availableGroups: Array.isArray(data.available_groups)
      ? data.available_groups
      : [],
  };
}

export async function fetchCurrentUser(): Promise<CurrentUserIdentity> {
  const res = await fetch('/api/me');
  if (!res.ok) throw new Error(`Could not load current user (${res.status}).`);
  const data: CurrentUserIdentity = await res.json();
  return normalizeIdentity(data);
}

function normalizeIdentity(
  identity?: Partial<CurrentUserIdentity>,
  fallbackEmail?: string | null,
): CurrentUserIdentity {
  const email =
    typeof identity?.email === 'string' && identity.email.trim()
      ? identity.email.trim()
      : fallbackEmail || null;
  const authenticated = identity?.authenticated ?? Boolean(email);
  return {
    email,
    authenticated: Boolean(authenticated && email),
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

export async function fetchResourceContent(url: string): Promise<string> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not load resource (${res.status}).`);
  return res.text();
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
