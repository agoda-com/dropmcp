import type {
  BenchmarkAggregate,
  BenchmarkStatus,
  BenchmarkSummary,
} from '../api/benchmarks';

export type Metric = 'latest' | 'history';
export type ModelSort = 'average' | 'name';

export interface BenchmarkView {
  metric: Metric;
  sort: ModelSort;
  compact: boolean;
  selected: string[] | null;
}

export const TOP_MODEL_COUNT = 5;

export function parseView(params: URLSearchParams): BenchmarkView {
  const models = (params.get('models') ?? '')
    .split(',')
    .map((name) => name.trim())
    .filter(Boolean);
  return {
    metric: params.get('metric') === 'history' ? 'history' : 'latest',
    sort: params.get('sort') === 'name' ? 'name' : 'average',
    compact: params.get('compact') === '1',
    selected: models.length > 0 ? models : null,
  };
}

export function viewToParams(
  view: BenchmarkView,
  base: URLSearchParams,
): URLSearchParams {
  const params = new URLSearchParams(base);
  for (const key of ['metric', 'sort', 'compact', 'models']) params.delete(key);
  if (view.metric === 'history') params.set('metric', 'history');
  if (view.sort === 'name') params.set('sort', 'name');
  if (view.compact) params.set('compact', '1');
  if (view.selected && view.selected.length > 0) {
    params.set('models', view.selected.join(','));
  }
  return params;
}

export function averageFor(summary: BenchmarkSummary, metric: Metric): number {
  return metric === 'history'
    ? summary.history.average_score
    : summary.average_score;
}

export function orderModels(
  models: string[],
  summary: Record<string, BenchmarkSummary>,
  metric: Metric,
  sort: ModelSort,
): string[] {
  const ordered = [...models];
  if (sort === 'name') return ordered.sort((a, b) => a.localeCompare(b));
  return ordered.sort((a, b) => {
    const gap = averageFor(summary[b], metric) - averageFor(summary[a], metric);
    return gap !== 0 ? gap : a.localeCompare(b);
  });
}

export function visibleModels(
  ordered: string[],
  selected: string[] | null,
): string[] {
  if (!selected) return ordered;
  const chosen = new Set(selected);
  const shown = ordered.filter((model) => chosen.has(model));
  return shown.length > 0 ? shown : ordered;
}

export function modelFamily(model: string): string {
  return model.split('-')[0].toLowerCase();
}

export function groupByFamily(models: string[]): [string, string[]][] {
  const groups = new Map<string, string[]>();
  for (const model of [...models].sort((a, b) => a.localeCompare(b))) {
    const family = modelFamily(model);
    groups.set(family, [...(groups.get(family) ?? []), model]);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

export function historyStatus(aggregate: BenchmarkAggregate): BenchmarkStatus {
  return aggregate.average_score >= aggregate.average_threshold ? 'pass' : 'fail';
}

export function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function deltaAgainstHistory(summary: BenchmarkSummary): number | null {
  if (summary.history.total <= summary.total) return null;
  const delta = summary.average_score - summary.history.average_score;
  return Math.abs(delta) >= 1 ? delta : null;
}

export function formatDelta(delta: number): string {
  return `${delta > 0 ? '▲' : '▼'}${formatNumber(Math.abs(delta))}`;
}

export function runTitle(run: {
  triggered_at: number;
  pipeline_id: string;
  commit_sha: string;
}): string {
  const date = run.triggered_at
    ? new Date(run.triggered_at).toISOString().slice(0, 10)
    : 'unknown date';
  const sha = run.commit_sha ? run.commit_sha.slice(0, 7) : 'unknown';
  return `Pipeline ${run.pipeline_id || 'unknown'} · ${sha} · ${date}`;
}

export function historyTitle(
  history: BenchmarkAggregate,
  lookbackDays: number,
): string {
  return `${lookbackDays}-day average ${formatNumber(history.average_score)} over ${history.total} ${history.total === 1 ? 'run' : 'runs'}`;
}

export function skillSubLine(
  aggregate: BenchmarkAggregate,
  metric: Metric,
  testCount: number,
): string {
  const threshold = `thr ${formatNumber(aggregate.average_threshold)}`;
  if (metric === 'history') {
    return `${threshold} · ${aggregate.passed}/${aggregate.total} runs`;
  }
  const partial = aggregate.total < testCount ? ` of ${testCount}` : '';
  return `${threshold} · ${aggregate.passed}/${aggregate.total}${partial}`;
}

export function overallSubLine(
  aggregate: BenchmarkAggregate,
  metric: Metric,
  testCount: number,
): string {
  if (metric === 'history') {
    return `${aggregate.passed}/${aggregate.total} runs passed`;
  }
  const coverage =
    aggregate.total < testCount ? ` · ${aggregate.total}/${testCount} tests` : '';
  return `${aggregate.passed}/${aggregate.total} passed${coverage}`;
}
