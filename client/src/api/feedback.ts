export type FeedbackStatus = 'new' | 'triaged' | 'actioned';
export type FeedbackType = 'correction' | 'agent_work';

export const FEEDBACK_STATUSES: FeedbackStatus[] = ['new', 'triaged', 'actioned'];
export const FEEDBACK_TYPES: FeedbackType[] = ['correction', 'agent_work'];

export interface FeedbackArtifact {
  kind?: string;
  action?: string;
  path?: string;
  language?: string;
  content?: string;
}

export interface FeedbackDetails {
  work_type?: string;
  summary?: string;
  artifacts?: FeedbackArtifact[];
  [key: string]: unknown;
}

export interface FeedbackItem {
  id: string;
  created_at: string;
  feedback_type?: FeedbackType;
  feedback: string;
  better_instruction: string;
  suggested_skill: string | null;
  model: string;
  client: string | null;
  skill_name: string | null;
  repo: string | null;
  details?: FeedbackDetails | null;
  status: FeedbackStatus;
  resolution_url: string | null;
}

interface FeedbackResponse {
  items: FeedbackItem[];
}

export interface FeedbackFilters {
  search?: string;
  model?: string;
  client?: string;
  skill_name?: string;
  feedback_type?: FeedbackType;
  status?: FeedbackStatus;
}

function buildQuery(filters: FeedbackFilters): string {
  const params = new URLSearchParams();
  if (filters.search) params.set('search', filters.search);
  if (filters.model) params.set('model', filters.model);
  if (filters.client) params.set('client', filters.client);
  if (filters.skill_name) params.set('skill_name', filters.skill_name);
  if (filters.feedback_type) params.set('feedback_type', filters.feedback_type);
  if (filters.status) params.set('status', filters.status);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export async function fetchFeedback(filters: FeedbackFilters = {}): Promise<FeedbackItem[]> {
  const res = await fetch(`/api/feedback${buildQuery(filters)}`);
  if (!res.ok) throw new Error(`Could not load feedback (${res.status}).`);
  const data: FeedbackResponse = await res.json();
  return Array.isArray(data.items) ? data.items : [];
}

export async function patchFeedback(
  id: string,
  body: { status?: FeedbackStatus; resolution_url?: string | null },
): Promise<FeedbackItem> {
  const res = await fetch(`/api/feedback/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Could not update feedback (${res.status}).`);
  return res.json();
}
