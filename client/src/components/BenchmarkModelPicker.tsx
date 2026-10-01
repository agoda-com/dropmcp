import type { BenchmarkSummary } from '../api/benchmarks';
import type { UpdateBenchmarkView } from '../hooks/useBenchmarkView';
import {
  TOP_MODEL_COUNT,
  groupByFamily,
  orderModels,
  type BenchmarkView,
} from '../utils/benchmarks';
import Pill from './Pill';
import styles from './BenchmarkControls.module.css';

interface Props {
  models: string[];
  shown: string[];
  summary: Record<string, BenchmarkSummary>;
  view: BenchmarkView;
  onChange: UpdateBenchmarkView;
}

export default function BenchmarkModelPicker({
  models,
  shown,
  summary,
  view,
  onChange,
}: Props) {
  const chosen = new Set(shown);

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
    <details className={styles.picker}>
      <summary>{`Models (${shown.length} of ${models.length})`}</summary>
      <div className={styles.pickerBody}>
        <ModelPresets
          models={models}
          chosen={chosen}
          summary={summary}
          view={view}
          onChange={onChange}
        />
        {groupByFamily(models).map(([family, members]) => (
          <ModelFamily
            key={family}
            family={family}
            members={members}
            chosen={chosen}
            onToggle={toggle}
          />
        ))}
      </div>
    </details>
  );
}

function ModelPresets({
  models,
  chosen,
  summary,
  view,
  onChange,
}: {
  models: string[];
  chosen: Set<string>;
  summary: Record<string, BenchmarkSummary>;
  view: BenchmarkView;
  onChange: UpdateBenchmarkView;
}) {
  const topModels = orderModels(models, summary, view.metric, 'average').slice(
    0,
    TOP_MODEL_COUNT,
  );
  const showingTop =
    chosen.size === topModels.length && topModels.every((model) => chosen.has(model));

  return (
    <div className={styles.family}>
      <span className={styles.familyName}>Presets</span>
      <Pill active={chosen.size === models.length} onClick={() => onChange({ selected: null })}>
        All
      </Pill>
      <Pill active={showingTop} onClick={() => onChange({ selected: topModels })}>
        {`Top ${TOP_MODEL_COUNT}`}
      </Pill>
    </div>
  );
}

function ModelFamily({
  family,
  members,
  chosen,
  onToggle,
}: {
  family: string;
  members: string[];
  chosen: Set<string>;
  onToggle: (model: string) => void;
}) {
  return (
    <div className={styles.family}>
      <span className={styles.familyName}>{family}</span>
      {members.map((model) => (
        <Pill key={model} active={chosen.has(model)} onClick={() => onToggle(model)}>
          {model}
        </Pill>
      ))}
    </div>
  );
}
