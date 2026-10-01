import type { BenchmarkSummary } from '../api/benchmarks';
import type { UpdateBenchmarkView } from '../hooks/useBenchmarkView';
import type { BenchmarkView } from '../utils/benchmarks';
import BenchmarkModelPicker from './BenchmarkModelPicker';
import Pill from './Pill';
import toolbarStyles from './FeedbackToolbar.module.css';
import styles from './BenchmarkControls.module.css';

interface Props {
  models: string[];
  shown: string[];
  summary: Record<string, BenchmarkSummary>;
  lookbackDays: number;
  view: BenchmarkView;
  onChange: UpdateBenchmarkView;
}

export default function BenchmarkControls({
  models,
  shown,
  summary,
  lookbackDays,
  view,
  onChange,
}: Props) {
  return (
    <div className={styles.controls}>
      <MetricFilter view={view} lookbackDays={lookbackDays} onChange={onChange} />

      <ModelSortFilter view={view} onChange={onChange} />

      <CompactToggle view={view} onChange={onChange} />

      <BenchmarkModelPicker
        models={models}
        shown={shown}
        summary={summary}
        view={view}
        onChange={onChange}
      />
    </div>
  );
}

function MetricFilter({
  view,
  lookbackDays,
  onChange,
}: {
  view: BenchmarkView;
  lookbackDays: number;
  onChange: UpdateBenchmarkView;
}) {
  return (
    <div className={toolbarStyles.filterRow}>
      <span className={toolbarStyles.filterLabel}>Show</span>
      <Pill active={view.metric === 'latest'} onClick={() => onChange({ metric: 'latest' })}>
        Latest
      </Pill>
      <Pill active={view.metric === 'history'} onClick={() => onChange({ metric: 'history' })}>
        {`${lookbackDays}-day average`}
      </Pill>
    </div>
  );
}

function ModelSortFilter({ view, onChange }: { view: BenchmarkView; onChange: UpdateBenchmarkView }) {
  return (
    <div className={toolbarStyles.filterRow}>
      <span className={toolbarStyles.filterLabel}>Sort models</span>
      <Pill active={view.sort === 'average'} onClick={() => onChange({ sort: 'average' })}>
        By average
      </Pill>
      <Pill active={view.sort === 'name'} onClick={() => onChange({ sort: 'name' })}>
        By name
      </Pill>
    </div>
  );
}

function CompactToggle({ view, onChange }: { view: BenchmarkView; onChange: UpdateBenchmarkView }) {
  return (
    <label className={styles.check}>
      <input
        type="checkbox"
        checked={view.compact}
        onChange={(event) => onChange({ compact: event.target.checked })}
      />
      Compact
    </label>
  );
}
