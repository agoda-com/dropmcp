import {
  REPO_FEEDBACK_CATEGORIES,
  REPO_FEEDBACK_STATUSES,
  type RepoFeedbackCategory,
  type RepoFeedbackSort,
  type RepoFeedbackStatus,
} from '../api/repoFeedback';
import { formatLabel } from '../utils/format';
import FeedbackOptionFilter from './FeedbackOptionFilter';
import FeedbackSearchField from './FeedbackSearchField';
import FeedbackValueFilter from './FeedbackValueFilter';
import styles from './FeedbackToolbar.module.css';

const STATUS_OPTIONS = ['all', ...REPO_FEEDBACK_STATUSES] as const;
const CATEGORY_OPTIONS = ['all', ...REPO_FEEDBACK_CATEGORIES] as const;
const SORT_OPTIONS = ['priority', 'recent'] as const;

export default function RepoFeedbackToolbar({
  search,
  onSearchChange,
  statusFilter,
  onStatusChange,
  categoryFilter,
  onCategoryChange,
  repoFilter,
  repos,
  onRepoChange,
  sortMode,
  onSortChange,
  models,
  modelFilter,
  onModelChange,
  clients,
  clientFilter,
  onClientChange,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: RepoFeedbackStatus | 'all';
  onStatusChange: (status: RepoFeedbackStatus | 'all') => void;
  categoryFilter: RepoFeedbackCategory | 'all';
  onCategoryChange: (category: RepoFeedbackCategory | 'all') => void;
  repoFilter: string | null;
  repos: string[];
  onRepoChange: (repo: string | null) => void;
  sortMode: RepoFeedbackSort;
  onSortChange: (sort: RepoFeedbackSort) => void;
  models: string[];
  modelFilter: string | null;
  onModelChange: (model: string | null) => void;
  clients: string[];
  clientFilter: string | null;
  onClientChange: (client: string | null) => void;
}) {
  return (
    <div className={styles.toolbar}>
      <FeedbackSearchField
        value={search}
        placeholder="Search summary or impact..."
        onChange={onSearchChange}
      />
      <FeedbackOptionFilter
        label="Status"
        options={STATUS_OPTIONS}
        value={statusFilter}
        optionLabel={(status) => (status === 'all' ? 'All' : status)}
        onChange={onStatusChange}
      />
      <FeedbackOptionFilter
        label="Category"
        options={CATEGORY_OPTIONS}
        value={categoryFilter}
        optionLabel={(category) => (category === 'all' ? 'All' : formatLabel(category))}
        onChange={onCategoryChange}
      />
      <FeedbackOptionFilter
        label="Sort"
        options={SORT_OPTIONS}
        value={sortMode}
        optionLabel={(sort) => (sort === 'priority' ? 'Priority' : 'Recent')}
        onChange={onSortChange}
      />

      {repos.length > 0 && (
        <FeedbackValueFilter
          label="Repo"
          values={repos}
          selected={repoFilter}
          onChange={onRepoChange}
        />
      )}

      {models.length > 0 && (
        <FeedbackValueFilter
          label="Model"
          values={models}
          selected={modelFilter}
          onChange={onModelChange}
        />
      )}

      {clients.length > 0 && (
        <FeedbackValueFilter
          label="Client"
          values={clients}
          selected={clientFilter}
          onChange={onClientChange}
        />
      )}
    </div>
  );
}
