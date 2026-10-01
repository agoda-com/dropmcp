import {
  FEEDBACK_STATUSES,
  FEEDBACK_TYPES,
  type FeedbackStatus,
  type FeedbackType,
} from '../api/feedback';
import FeedbackOptionFilter from './FeedbackOptionFilter';
import FeedbackSearchField from './FeedbackSearchField';
import FeedbackValueFilter from './FeedbackValueFilter';
import styles from './FeedbackToolbar.module.css';

const STATUS_OPTIONS = ['all', ...FEEDBACK_STATUSES] as const;
const TYPE_OPTIONS = ['all', ...FEEDBACK_TYPES] as const;

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
      <FeedbackSearchField
        value={search}
        placeholder="Search feedback or better instruction…"
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
        label="Type"
        options={TYPE_OPTIONS}
        value={typeFilter}
        optionLabel={typeLabel}
        onChange={onTypeChange}
      />

      {models.length > 0 && (
        <FeedbackValueFilter label="Model" values={models} selected={modelFilter} onChange={onModelChange} />
      )}

      {clients.length > 0 && (
        <FeedbackValueFilter label="Client" values={clients} selected={clientFilter} onChange={onClientChange} />
      )}
    </div>
  );
}

function typeLabel(type: FeedbackType | 'all'): string {
  return type === 'all' ? 'All' : type === 'agent_work' ? 'agent work' : type;
}
