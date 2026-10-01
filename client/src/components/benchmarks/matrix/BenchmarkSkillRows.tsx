import { useState } from 'react';
import type { BenchmarkSkill } from '../../../api/benchmarks';
import type { BenchmarkView } from '../../../utils/benchmarks';
import BenchmarkOverallCell from './BenchmarkOverallCell';
import BenchmarkSkillCell from './BenchmarkSkillCell';
import BenchmarkTestRow from './BenchmarkTestRow';
import styles from './BenchmarkMatrix.module.css';

interface Props {
  skill: BenchmarkSkill;
  models: string[];
  view: BenchmarkView;
  lookbackDays: number;
}

export default function BenchmarkSkillRows({ skill, models, view, lookbackDays }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr>
        <th scope="row" className={styles.nameCol}>
          <SkillToggle
            skill={skill}
            expanded={expanded}
            onToggle={() => setExpanded((value) => !value)}
          />
        </th>
        <BenchmarkOverallCell
          summary={skill.overall}
          testCount={0}
          view={view}
          lookbackDays={lookbackDays}
          className={styles.allCol}
        />
        {models.map((model) => (
          <BenchmarkSkillCell
            key={model}
            cell={skill.cells[model]}
            testCount={skill.test_count}
            view={view}
            lookbackDays={lookbackDays}
          />
        ))}
      </tr>

      {expanded &&
        skill.tests.map((test) => (
          <BenchmarkTestRow
            key={test.name}
            skillName={skill.name}
            test={test}
            models={models}
            view={view}
            lookbackDays={lookbackDays}
          />
        ))}
    </>
  );
}

function SkillToggle({
  skill,
  expanded,
  onToggle,
}: {
  skill: BenchmarkSkill;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      className={styles.toggle}
      aria-expanded={expanded}
      onClick={onToggle}
    >
      <span className={styles.chevron} aria-hidden="true">▸</span>
      <span>{skill.name}</span>
      <span className={styles.count}>
        {skill.test_count} {skill.test_count === 1 ? 'test' : 'tests'}
      </span>
    </button>
  );
}
