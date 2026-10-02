import { useCallback, useEffect, useRef, useState } from 'react';
import {
  fetchMemories,
  fetchMemoryStats,
  fetchOpenReports,
  type MemoryListItem,
  type MemoryReport,
  type MemorySort,
  type MemoryStatsPeriod,
  type MemoryStatus,
} from '../api/memory';
import FeedbackHeader from '../components/FeedbackHeader';
import MemoryDetailsPanel from '../components/memory/MemoryDetailsPanel';
import MemoryList from '../components/memory/MemoryList';
import MemoryOpenReports from '../components/memory/MemoryOpenReports';
import MemoryStatsStrip from '../components/memory/MemoryStatsStrip';
import MemoryToolbar from '../components/memory/MemoryToolbar';
import pageStyles from './MemoryPage.module.css';

export default function MemoryPage() {
  const [items, setItems] = useState<MemoryListItem[]>([]);
  const [repos, setRepos] = useState<string[]>([]);
  const [languages, setLanguages] = useState<string[]>([]);
  const [kinds, setKinds] = useState<string[]>([]);
  const [periods, setPeriods] = useState<MemoryStatsPeriod[]>([]);
  const [openReports, setOpenReports] = useState<MemoryReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [repo, setRepo] = useState<string | null>(null);
  const [language, setLanguage] = useState<string | null>(null);
  const [kind, setKind] = useState('all');
  const [status, setStatus] = useState<MemoryStatus | 'all'>('all');
  const [visibility, setVisibility] = useState<'all' | 'hidden'>('all');
  const [sort, setSort] = useState<MemorySort>('confirmations');
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const loadGeneration = useRef(0);

  const loadList = useCallback(async () => {
    const generation = ++loadGeneration.current;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchMemories({
        search: search.trim() || undefined,
        repo: repo ?? undefined,
        language: language ?? undefined,
        kind: kind === 'all' ? undefined : kind,
        status: status === 'all' ? undefined : status,
        hidden: visibility === 'hidden' ? true : undefined,
        sort,
      });
      if (generation !== loadGeneration.current) return;
      setItems(data.items);
      setRepos(data.repos);
      setLanguages(data.languages);
      setKinds(data.kinds);
    } catch (err) {
      if (generation !== loadGeneration.current) return;
      setError(err instanceof Error ? err.message : 'Failed to load memories.');
    } finally {
      if (generation === loadGeneration.current) setLoading(false);
    }
  }, [search, repo, language, kind, status, visibility, sort]);

  useEffect(() => {
    const timer = setTimeout(loadList, search ? 250 : 0);
    return () => clearTimeout(timer);
  }, [loadList, search]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchMemoryStats(), fetchOpenReports()])
      .then(([stats, reports]) => {
        if (cancelled) return;
        setPeriods(stats.periods);
        setOpenReports(reports);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleDeleted(key: string) {
    setItems((current) => current.filter((item) => item.key !== key));
    setSelectedKey(null);
    fetchOpenReports()
      .then(setOpenReports)
      .catch(() => undefined);
    fetchMemoryStats()
      .then((stats) => setPeriods(stats.periods))
      .catch(() => undefined);
  }

  return (
    <main className={pageStyles.page}>
      <FeedbackHeader
        title="Memory"
        description="Memories, hidden memories, open reports and recall stats."
      />
      <MemoryStatsStrip periods={periods} />
      <MemoryToolbar
        search={search}
        onSearchChange={setSearch}
        kind={kind}
        kinds={kinds}
        onKindChange={setKind}
        status={status}
        onStatusChange={setStatus}
        sort={sort}
        onSortChange={setSort}
        visibility={visibility}
        onVisibilityChange={setVisibility}
        repo={repo}
        repos={repos}
        onRepoChange={setRepo}
        language={language}
        languages={languages}
        onLanguageChange={setLanguage}
      />
      <MemoryList
        loading={loading}
        error={error}
        items={items}
        selectedKey={selectedKey}
        onSelect={setSelectedKey}
      />
      {selectedKey && (
        <MemoryDetailsPanel memoryKey={selectedKey} onDeleted={handleDeleted} />
      )}
      <MemoryOpenReports reports={openReports} />
    </main>
  );
}
