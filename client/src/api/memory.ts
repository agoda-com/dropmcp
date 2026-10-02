export type MemorySort = 'confirmations' | 'recent';
export type MemoryStatus = 'active' | 'superseded' | 'retired';

export const MEMORY_STATUSES: MemoryStatus[] = ['active', 'superseded', 'retired'];

export interface MemoryListItem {
  key: string;
  title: string;
  kind: string;
  status: string;
  repo: string | null;
  language: string | null;
  scope: string;
  confirmations: number;
  confirmations_label: string;
  open_reports: number;
  open_reports_label: string;
  hidden: boolean;
  hidden_label: string | null;
  display_created_at: string | null;
  display_confirmed_at: string | null;
}

export interface MemoryDetail extends MemoryListItem {
  body: string;
  evidence: string | null;
}

export interface MemoryReport {
  id: string;
  problem: string;
  problem_label: string;
  reason: string | null;
  correction: string | null;
  status: string;
  reported_key: string | null;
  memory_key: string | null;
  described_memory: string | null;
  candidate_keys: string[];
  candidate_keys_label: string | null;
  keyed: boolean;
  link_label: string;
  display_created_at: string | null;
}

export interface MemoryStatsPeriod {
  days: number;
  label: string;
  recall_count: number;
  recalls_with_results: number;
  recalls_without_results: number;
  share_returning: string;
  report_count: number;
  reports_per_recall: string;
  distinct_writers: number;
}

export interface MemoryListResponse {
  items: MemoryListItem[];
  repos: string[];
  languages: string[];
  kinds: string[];
}

export interface MemoryDetailResponse {
  memory: MemoryDetail;
  reports: MemoryReport[];
}

export interface MemoryReportsResponse {
  items: MemoryReport[];
}

export interface MemoryStatsResponse {
  periods: MemoryStatsPeriod[];
}

export interface MemoryFilters {
  search?: string;
  repo?: string;
  language?: string;
  kind?: string;
  status?: MemoryStatus;
  hidden?: boolean;
  sort?: MemorySort;
}

const SIGN_IN_TO_VIEW = 'Sign in to view memories.';

function buildQuery(filters: MemoryFilters): string {
  const params = new URLSearchParams();
  if (filters.search) params.set('search', filters.search);
  if (filters.repo) params.set('repo', filters.repo);
  if (filters.language) params.set('language', filters.language);
  if (filters.kind) params.set('kind', filters.kind);
  if (filters.status) params.set('status', filters.status);
  if (filters.hidden) params.set('hidden', 'true');
  if (filters.sort) params.set('sort', filters.sort);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export async function fetchMemories(
  filters: MemoryFilters = {},
): Promise<MemoryListResponse> {
  const res = await fetch(`/api/memory${buildQuery(filters)}`);
  if (res.status === 401) throw new Error(SIGN_IN_TO_VIEW);
  if (!res.ok) throw new Error(`Could not load memories (${res.status}).`);
  const data: MemoryListResponse = await res.json();
  return {
    items: Array.isArray(data.items) ? data.items : [],
    repos: Array.isArray(data.repos) ? data.repos : [],
    languages: Array.isArray(data.languages) ? data.languages : [],
    kinds: Array.isArray(data.kinds) ? data.kinds : [],
  };
}

export async function fetchMemory(key: string): Promise<MemoryDetailResponse> {
  const res = await fetch(`/api/memory/${encodeURIComponent(key)}`);
  if (res.status === 401) throw new Error(SIGN_IN_TO_VIEW);
  if (!res.ok) throw new Error(`Could not load memory (${res.status}).`);
  return res.json();
}

export async function fetchOpenReports(): Promise<MemoryReport[]> {
  const res = await fetch('/api/memory/reports');
  if (res.status === 401) throw new Error(SIGN_IN_TO_VIEW);
  if (!res.ok) throw new Error(`Could not load reports (${res.status}).`);
  const data: MemoryReportsResponse = await res.json();
  return Array.isArray(data.items) ? data.items : [];
}

export async function fetchMemoryStats(): Promise<MemoryStatsResponse> {
  const res = await fetch('/api/memory/stats');
  if (res.status === 401) throw new Error(SIGN_IN_TO_VIEW);
  if (!res.ok) throw new Error(`Could not load recall stats (${res.status}).`);
  const data: MemoryStatsResponse = await res.json();
  return { periods: Array.isArray(data.periods) ? data.periods : [] };
}

export async function deleteMemory(key: string): Promise<void> {
  const res = await fetch(`/api/memory/${encodeURIComponent(key)}`, {
    method: 'DELETE',
  });
  if (res.status === 401) throw new Error('Sign in to delete a memory.');
  if (!res.ok) throw new Error(`Could not delete memory (${res.status}).`);
}
