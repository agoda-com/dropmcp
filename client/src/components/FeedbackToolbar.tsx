import {
  FEEDBACK_STATUSES,
  FEEDBACK_TYPES,
  type FeedbackStatus,
  type FeedbackType,
} from '../api/feedback';
import styles from './FeedbackToolbar.module.css';

interface Props {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: FeedbackStatus | 'all';
  onStatusChange: (status: FeedbackStatus | 'all') => void;
  typeFilter: FeedbackType | 'all';
  onTypeChange: (type: FeedbackType | 'all') => void;
  models: string[];
  modelFilter: string | null;
  onModelChange: (model: string | null) => void;
  clients: string[];
  clientFilter: string | null;
  onClientChange: (client: string | null) => void;
}

export default function FeedbackToolbar({
  search,
  onSearchChange,
  statusFilter,
  onStatusChange,
  typeFilter,
  onTypeChange,
  models,
  modelFilter,
  onModelChange,
  clients,
  clientFilter,
  onClientChange,
}: Props) {
  return (
    <div className={styles.toolbar}>
      <SearchField value={search} onChange={onSearchChange} />

      <StatusFilter value={statusFilter} onChange={onStatusChange} />

      <TypeFilter value={typeFilter} onChange={onTypeChange} />

      {models.length > 0 && (
        <ValueFilter label="Model" values={models} selected={modelFilter} onChange={onModelChange} />
      )}

      {clients.length > 0 && (
        <ValueFilter label="Client" values={clients} selected={clientFilter} onChange={onClientChange} />
      )}
    </div>
  );
}

function SearchField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className={styles.searchWrap}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="11" cy="11" r="7" />
        <path d="M21 21l-4.35-4.35" />
      </svg>
      <input
        type="search"
        className={styles.searchInput}
        placeholder="Search feedback or better instruction…"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

function StatusFilter({
  value,
  onChange,
}: {
  value: FeedbackStatus | 'all';
  onChange: (status: FeedbackStatus | 'all') => void;
}) {
  return (
    <div className={styles.filterRow}>
      <span className={styles.filterLabel}>Status</span>
      {(['all', ...FEEDBACK_STATUSES] as const).map((status) => (
        <button
          key={status}
          type="button"
          className={`${styles.pill} ${value === status ? styles.pillActive : ''}`}
          onClick={() => onChange(status)}
        >
          {status === 'all' ? 'All' : status}
        </button>
      ))}
    </div>
  );
}

function TypeFilter({
  value,
  onChange,
}: {
  value: FeedbackType | 'all';
  onChange: (type: FeedbackType | 'all') => void;
}) {
  return (
    <div className={styles.filterRow}>
      <span className={styles.filterLabel}>Type</span>
      {(['all', ...FEEDBACK_TYPES] as const).map((type) => (
        <button
          key={type}
          type="button"
          className={`${styles.pill} ${value === type ? styles.pillActive : ''}`}
          onClick={() => onChange(type)}
        >
          {type === 'all' ? 'All' : type === 'agent_work' ? 'agent work' : type}
        </button>
      ))}
    </div>
  );
}

function ValueFilter({
  label,
  values,
  selected,
  onChange,
}: {
  label: string;
  values: string[];
  selected: string | null;
  onChange: (value: string | null) => void;
}) {
  return (
    <div className={styles.filterRow}>
      <span className={styles.filterLabel}>{label}</span>
      <button
        type="button"
        className={`${styles.pill} ${selected === null ? styles.pillActive : ''}`}
        onClick={() => onChange(null)}
      >
        All
      </button>
      {values.map((value) => (
        <button
          key={value}
          type="button"
          className={`${styles.pill} ${selected === value ? styles.pillActive : ''}`}
          onClick={() => onChange(selected === value ? null : value)}
        >
          {value}
        </button>
      ))}
    </div>
  );
}
