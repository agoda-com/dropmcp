import {
  MEMORY_STATUSES,
  type MemorySort,
  type MemoryStatus,
} from '../../api/memory';
import FeedbackOptionFilter from '../feedback/FeedbackOptionFilter';
import FeedbackSearchField from '../feedback/FeedbackSearchField';
import FeedbackValueFilter from '../feedback/FeedbackValueFilter';
import toolbarStyles from '../feedback/FeedbackToolbar.module.css';

const SORT_OPTIONS = ['confirmations', 'recent'] as const;
const VISIBILITY_OPTIONS = ['all', 'hidden'] as const;

export default function MemoryToolbar({
  search,
  onSearchChange,
  kind,
  kinds,
  onKindChange,
  status,
  onStatusChange,
  sort,
  onSortChange,
  visibility,
  onVisibilityChange,
  repo,
  repos,
  onRepoChange,
  language,
  languages,
  onLanguageChange,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  kind: string;
  kinds: string[];
  onKindChange: (kind: string) => void;
  status: MemoryStatus | 'all';
  onStatusChange: (status: MemoryStatus | 'all') => void;
  sort: MemorySort;
  onSortChange: (sort: MemorySort) => void;
  visibility: 'all' | 'hidden';
  onVisibilityChange: (visibility: 'all' | 'hidden') => void;
  repo: string | null;
  repos: string[];
  onRepoChange: (repo: string | null) => void;
  language: string | null;
  languages: string[];
  onLanguageChange: (language: string | null) => void;
}) {
  return (
    <div className={toolbarStyles.toolbar}>
      <FeedbackSearchField
        value={search}
        placeholder="Search title or body..."
        onChange={onSearchChange}
      />
      <div role="group" aria-label="Kind">
        <FeedbackOptionFilter
          label="Kind"
          options={['all', ...kinds]}
          value={kind}
          optionLabel={(option) => (option === 'all' ? 'All' : option)}
          onChange={onKindChange}
        />
      </div>
      <div role="group" aria-label="Status">
        <FeedbackOptionFilter
          label="Status"
          options={['all', ...MEMORY_STATUSES]}
          value={status}
          optionLabel={(option) => (option === 'all' ? 'All' : option)}
          onChange={onStatusChange}
        />
      </div>
      <div role="group" aria-label="Sort">
        <FeedbackOptionFilter
          label="Sort"
          options={SORT_OPTIONS}
          value={sort}
          optionLabel={(option) => (option === 'recent' ? 'Recent' : 'Confirmations')}
          onChange={onSortChange}
        />
      </div>
      <div role="group" aria-label="Visibility">
        <FeedbackOptionFilter
          label="Visibility"
          options={VISIBILITY_OPTIONS}
          value={visibility}
          optionLabel={(option) => (option === 'hidden' ? 'Hidden' : 'All')}
          onChange={onVisibilityChange}
        />
      </div>
      {repos.length > 0 && (
        <div role="group" aria-label="Repo">
          <FeedbackValueFilter
            label="Repo"
            values={repos}
            selected={repo}
            onChange={onRepoChange}
          />
        </div>
      )}
      {languages.length > 0 && (
        <div role="group" aria-label="Language">
          <FeedbackValueFilter
            label="Language"
            values={languages}
            selected={language}
            onChange={onLanguageChange}
          />
        </div>
      )}
    </div>
  );
}
