export type RepoFeedbackStatus = 'new' | 'triaged' | 'actioned' | 'wontfix';
export type RepoFeedbackCategory =
  | 'tests_require_ci'
  | 'flaky_test'
  | 'build_warnings'
  | 'lint_noise'
  | 'slow_feedback'
  | 'local_setup'
  | 'docs_gap'
  | 'dependency_issue'
  | 'tooling_gap'
  | 'other';

export const REPO_FEEDBACK_STATUSES: RepoFeedbackStatus[] = [
  'new',
  'triaged',
  'actioned',
  'wontfix',
];

export const REPO_FEEDBACK_CATEGORIES: RepoFeedbackCategory[] = [
  'tests_require_ci',
  'flaky_test',
  'build_warnings',
  'lint_noise',
  'slow_feedback',
  'local_setup',
  'docs_gap',
  'dependency_issue',
  'tooling_gap',
  'other',
];

export type RepoFeedbackDetails = Record<string, unknown>;

export type RepoFeedbackSort = 'priority' | 'recent';

export interface RepoFeedbackItem {
  id: string;
  created_at: string;
  last_seen_at: string;
  category: RepoFeedbackCategory;
  repo: string;
  summary: string;
  impact: string;
  suggested_fix: string | null;
  model: string;
  client: string | null;
  details?: RepoFeedbackDetails | null;
  fingerprint: string;
  occurrence_count: number;
  status: RepoFeedbackStatus;
  resolution_url: string | null;
}

interface RepoFeedbackResponse {
  items: RepoFeedbackItem[];
}

export interface RepoFeedbackFilters {
  search?: string;
  repo?: string;
  category?: RepoFeedbackCategory;
  status?: RepoFeedbackStatus;
  model?: string;
  client?: string;
  sort?: RepoFeedbackSort;
}

function buildQuery(filters: RepoFeedbackFilters): string {
  const params = new URLSearchParams();
  if (filters.search) params.set('search', filters.search);
  if (filters.repo) params.set('repo', filters.repo);
  if (filters.category) params.set('category', filters.category);
  if (filters.status) params.set('status', filters.status);
  if (filters.model) params.set('model', filters.model);
  if (filters.client) params.set('client', filters.client);
  if (filters.sort === 'recent') params.set('sort', filters.sort);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export async function fetchRepoFeedback(
  filters: RepoFeedbackFilters = {},
): Promise<RepoFeedbackItem[]> {
  const res = await fetch(`/api/repo-feedback${buildQuery(filters)}`);
  if (!res.ok) throw new Error(`Could not load repo feedback (${res.status}).`);
  const data: RepoFeedbackResponse = await res.json();
  return Array.isArray(data.items) ? data.items : [];
}

export async function patchRepoFeedback(
  id: string,
  body: { status?: RepoFeedbackStatus; resolution_url?: string | null },
): Promise<RepoFeedbackItem> {
  const res = await fetch(`/api/repo-feedback/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Could not update repo feedback (${res.status}).`);
  return res.json();
}
