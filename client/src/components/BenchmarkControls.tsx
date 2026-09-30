import type { BenchmarkSummary } from '../api/benchmarks';
import {
  TOP_MODEL_COUNT,
  groupByFamily,
  orderModels,
  type BenchmarkView,
} from '../utils/benchmarks';
import toolbarStyles from './FeedbackToolbar.module.css';
import styles from './BenchmarkControls.module.css';

interface Props {
  models: string[];
  shown: string[];
  summary: Record<string, BenchmarkSummary>;
  lookbackDays: number;
  view: BenchmarkView;
  onChange: (patch: Partial<BenchmarkView>) => void;
}

function Pill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={`${toolbarStyles.pill} ${active ? toolbarStyles.pillActive : ''}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export default function BenchmarkControls({
  models,
  shown,
  summary,
  lookbackDays,
  view,
  onChange,
}: Props) {
  const chosen = new Set(shown);
  const topModels = orderModels(models, summary, view.metric, 'average').slice(
    0,
    TOP_MODEL_COUNT,
  );

  function toggle(model: string) {
    const next = new Set(chosen);
    if (next.has(model)) {
      if (next.size === 1) return;
      next.delete(model);
    } else {
      next.add(model);
    }
    onChange({ selected: next.size === models.length ? null : [...next] });
  }

  return (
    <div className={styles.controls}>
      <div className={toolbarStyles.filterRow}>
        <span className={toolbarStyles.filterLabel}>Show</span>
        <Pill active={view.metric === 'latest'} onClick={() => onChange({ metric: 'latest' })}>
          Latest
        </Pill>
        <Pill active={view.metric === 'history'} onClick={() => onChange({ metric: 'history' })}>
          {`${lookbackDays}-day average`}
        </Pill>
      </div>

      <div className={toolbarStyles.filterRow}>
        <span className={toolbarStyles.filterLabel}>Sort models</span>
        <Pill active={view.sort === 'average'} onClick={() => onChange({ sort: 'average' })}>
          By average
        </Pill>
        <Pill active={view.sort === 'name'} onClick={() => onChange({ sort: 'name' })}>
          By name
        </Pill>
      </div>

      <label className={styles.check}>
        <input
          type="checkbox"
          checked={view.compact}
          onChange={(event) => onChange({ compact: event.target.checked })}
        />
        Compact
      </label>

      <details className={styles.picker}>
        <summary>{`Models (${shown.length} of ${models.length})`}</summary>
        <div className={styles.pickerBody}>
          <div className={styles.family}>
            <span className={styles.familyName}>Presets</span>
            <Pill active={shown.length === models.length} onClick={() => onChange({ selected: null })}>
              All
            </Pill>
            <Pill
              active={
                shown.length === topModels.length &&
                topModels.every((model) => chosen.has(model))
              }
              onClick={() => onChange({ selected: topModels })}
            >
              {`Top ${TOP_MODEL_COUNT}`}
            </Pill>
          </div>
          {groupByFamily(models).map(([family, members]) => (
            <div key={family} className={styles.family}>
              <span className={styles.familyName}>{family}</span>
              {members.map((model) => (
                <Pill key={model} active={chosen.has(model)} onClick={() => toggle(model)}>
                  {model}
                </Pill>
              ))}
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
