import type { BenchmarkSkill, BenchmarkSummary } from '../api/benchmarks';
import type { BenchmarkView } from '../utils/benchmarks';
import BenchmarkHeaderRow from './BenchmarkHeaderRow';
import BenchmarkOverallRow from './BenchmarkOverallRow';
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
          <BenchmarkHeaderRow models={models} />
          <BenchmarkOverallRow
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
