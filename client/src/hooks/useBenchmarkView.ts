import { useSearchParams } from 'react-router-dom';
import { parseView, viewToParams, type BenchmarkView } from '../utils/benchmarks';

export type UpdateBenchmarkView = (patch: Partial<BenchmarkView>) => void;

export function useBenchmarkView(): [BenchmarkView, UpdateBenchmarkView] {
  const [params, setParams] = useSearchParams();

  function updateView(patch: Partial<BenchmarkView>) {
    setParams(
      (current) => viewToParams({ ...parseView(current), ...patch }, current),
      { replace: true },
    );
  }

  return [parseView(params), updateView];
}
