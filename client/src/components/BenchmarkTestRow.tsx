import type { BenchmarkTest } from '../api/benchmarks';
import type { BenchmarkView } from '../utils/benchmarks';
import BenchmarkTestCell from './BenchmarkTestCell';
import styles from './BenchmarkMatrix.module.css';

interface Props {
  skillName: string;
  test: BenchmarkTest;
  models: string[];
  view: BenchmarkView;
  lookbackDays: number;
}

export default function BenchmarkTestRow({
  skillName,
  test,
  models,
  view,
  lookbackDays,
}: Props) {
  return (
    <tr className={styles.testRow}>
      <th scope="row" className={styles.nameCol} title={test.name}>
        {testLabel(skillName, test.name)}
      </th>
      <td className={styles.missing} />
      {models.map((model) => (
        <BenchmarkTestCell
          key={model}
          run={test.results[model]}
          view={view}
          lookbackDays={lookbackDays}
        />
      ))}
    </tr>
  );
}

function testLabel(skill: string, test: string): string {
  return test.startsWith(`${skill}/`) ? test.slice(skill.length + 1) : test;
}
