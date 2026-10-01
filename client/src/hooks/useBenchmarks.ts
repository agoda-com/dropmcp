import { useQuery } from '@tanstack/react-query';
import { fetchBenchmarks } from '../api/benchmarks';
import { useCatalog } from '../context/CatalogContext';

export function useBenchmarks() {
  const { benchmarksEnabled, loading: catalogLoading } = useCatalog();
  const { data = null, error, isLoading } = useQuery({
    queryKey: ['benchmarks'],
    queryFn: fetchBenchmarks,
    enabled: !catalogLoading && benchmarksEnabled,
    retry: false,
    staleTime: 60_000,
  });

  return {
    catalogLoading,
    enabled: benchmarksEnabled,
    loading: isLoading,
    error: error?.message ?? null,
    data,
  };
}
