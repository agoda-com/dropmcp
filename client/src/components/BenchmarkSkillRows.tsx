import { useState } from 'react';
import type { BenchmarkSkill, BenchmarkTest } from '../api/benchmarks';
import type { BenchmarkView } from '../utils/benchmarks';
import { OverallCell, SkillCell, TestCell } from './BenchmarkCells';
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
        <OverallCell
          summary={skill.overall}
          testCount={0}
          view={view}
          lookbackDays={lookbackDays}
          className={styles.allCol}
        />
        {models.map((model) => (
          <SkillCell
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
          <TestRow
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

function TestRow({
  skillName,
  test,
  models,
  view,
  lookbackDays,
}: Omit<Props, 'skill'> & { skillName: string; test: BenchmarkTest }) {
  return (
    <tr className={styles.testRow}>
      <th scope="row" className={styles.nameCol} title={test.name}>
        {testLabel(skillName, test.name)}
      </th>
      <td className={styles.missing} />
      {models.map((model) => (
        <TestCell
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
