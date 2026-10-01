export type BenchmarkStatus = 'pass' | 'partial' | 'fail';

export interface BenchmarkAggregate {
  average_score: number;
  average_threshold: number;
  passed: number;
  total: number;
  status: BenchmarkStatus;
}

export interface BenchmarkSummary extends BenchmarkAggregate {
  history: BenchmarkAggregate;
}

export interface BenchmarkCell extends BenchmarkSummary {
  triggered_at: number;
  pipeline_id: string;
  commit_sha: string;
}

export interface BenchmarkRun {
  passed: boolean;
  score: number;
  threshold: number;
  triggered_at: number;
  pipeline_id: string;
  commit_sha: string;
  history: BenchmarkAggregate;
  series: number[];
}

export interface BenchmarkTest {
  name: string;
  results: Record<string, BenchmarkRun>;
}

export interface BenchmarkSkill {
  name: string;
  test_count: number;
  overall: BenchmarkSummary;
  cells: Record<string, BenchmarkCell>;
  tests: BenchmarkTest[];
}

export interface BenchmarksResponse {
  project: string;
  lookback_days: number;
  generated_at: string;
  error: string | null;
  models: string[];
  test_count: number;
  summary: Record<string, BenchmarkSummary>;
  skills: BenchmarkSkill[];
}

export async function fetchBenchmarks(): Promise<BenchmarksResponse> {
  const res = await fetch('/api/benchmarks', {
    headers: { Accept: 'application/json' },
  });
  if (res.status === 401) {
    throw new Error('Sign in to view benchmark results.');
  }
  if (!res.ok) throw new Error(`Could not load benchmarks (${res.status}).`);
  return res.json();
}
