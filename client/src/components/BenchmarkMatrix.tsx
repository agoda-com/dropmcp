import type { BenchmarkSkill, BenchmarkSummary } from '../api/benchmarks';
import type { BenchmarkView } from '../utils/benchmarks';
import { EmptyCell, OverallCell } from './BenchmarkCells';
import BenchmarkSkillRows from './BenchmarkSkillRows';
import styles from './BenchmarkMatrix.module.css';

interface Props {
  skills: BenchmarkSkill[];
  models: string[];
  summary: Record<string, BenchmarkSummary>;
  testCount: number;
  lookbackDays: number;
  view: BenchmarkView;
}

export default function BenchmarkMatrix({
  skills,
  models,
  summary,
  testCount,
  lookbackDays,
  view,
}: Props) {
  return (
    <div className={styles.scroll}>
      <table className={`${styles.table} ${view.compact ? styles.compact : ''}`}>
        <thead>
          <ModelHeaderRow models={models} />
          <OverallRow
            models={models}
            summary={summary}
            testCount={testCount}
            lookbackDays={lookbackDays}
            view={view}
          />
        </thead>
        <tbody>
          {skills.map((skill) => (
            <BenchmarkSkillRows
              key={skill.name}
              skill={skill}
              models={models}
              view={view}
              lookbackDays={lookbackDays}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ModelHeaderRow({ models }: { models: string[] }) {
  return (
    <tr>
      <th scope="col" className={styles.nameCol}>Skill</th>
      <th scope="col" className={styles.allCol}>All models</th>
      {models.map((model) => (
        <th key={model} scope="col" title={model}>{model}</th>
      ))}
    </tr>
  );
}

function OverallRow({
  models,
  summary,
  testCount,
  lookbackDays,
  view,
}: Omit<Props, 'skills'>) {
  return (
    <tr className={styles.overallRow}>
      <th scope="row" className={styles.nameCol}>
        Overall
        <span className={styles.count}>{testCount} tests</span>
      </th>
      <EmptyCell />
      {models.map((model) => (
        <OverallCell
          key={model}
          summary={summary[model]}
          testCount={testCount}
          view={view}
          lookbackDays={lookbackDays}
        />
      ))}
    </tr>
  );
}
