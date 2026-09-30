import { useState } from 'react';
import type {
  BenchmarkAggregate,
  BenchmarkCell,
  BenchmarkStatus,
  BenchmarkRun,
  BenchmarkSkill,
  BenchmarkSummary,
} from '../api/benchmarks';
import {
  deltaAgainstHistory,
  formatDelta,
  formatNumber,
  historyStatus,
  historyTitle,
  overallSubLine,
  runTitle,
  skillSubLine,
  type BenchmarkView,
  type Metric,
} from '../utils/benchmarks';
import styles from './BenchmarkMatrix.module.css';

interface Props {
  skills: BenchmarkSkill[];
  models: string[];
  summary: Record<string, BenchmarkSummary>;
  testCount: number;
  lookbackDays: number;
  view: BenchmarkView;
}

function Sparkline({ values }: { values: number[] }) {
  const width = 56;
  const height = 14;
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  const points = values
    .map((value, index) => {
      const x = 1 + (index / (values.length - 1)) * (width - 2);
      const y = height - 1 - ((value - min) / span) * (height - 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <svg
      className={styles.sparkline}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
    >
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function ScoreCell({
  source,
  delta,
  sub,
  compact,
  title,
  status,
  extraClass = '',
}: {
  source: BenchmarkAggregate;
  delta: number | null;
  sub: string;
  compact: boolean;
  title: string;
  status: BenchmarkStatus;
  extraClass?: string;
}) {
  return (
    <td className={`${styles[status]} ${extraClass}`} title={title}>
      <span className={styles.score}>
        {formatNumber(source.average_score)}
        {delta !== null && !compact && (
          <span className={delta > 0 ? styles.up : styles.down}>
            {formatDelta(delta)}
          </span>
        )}
      </span>
      {!compact && <span className={styles.sub}>{sub}</span>}
    </td>
  );
}

function SkillCell({
  cell,
  metric,
  compact,
  testCount,
  lookbackDays,
}: {
  cell: BenchmarkCell | undefined;
  metric: Metric;
  compact: boolean;
  testCount: number;
  lookbackDays: number;
}) {
  if (!cell) return <td className={styles.missing}>—</td>;
  const source = metric === 'history' ? cell.history : cell;

  return (
    <ScoreCell
      source={source}
      delta={metric === 'latest' ? deltaAgainstHistory(cell) : null}
      sub={skillSubLine(source, metric, testCount)}
      compact={compact}
      title={`${runTitle(cell)}\n${historyTitle(cell.history, lookbackDays)}`}
      status={metric === 'history' ? historyStatus(source) : source.status}
    />
  );
}

function OverallCell({
  summary,
  metric,
  compact,
  testCount,
  lookbackDays,
  extraClass,
}: {
  summary: BenchmarkSummary;
  metric: Metric;
  compact: boolean;
  testCount: number;
  lookbackDays: number;
  extraClass?: string;
}) {
  const source = metric === 'history' ? summary.history : summary;

  return (
    <ScoreCell
      source={source}
      delta={metric === 'latest' ? deltaAgainstHistory(summary) : null}
      sub={overallSubLine(source, metric, testCount)}
      compact={compact}
      title={historyTitle(summary.history, lookbackDays)}
      status={metric === 'history' ? historyStatus(source) : source.status}
      extraClass={extraClass}
    />
  );
}

function TestCell({
  run,
  metric,
  compact,
  lookbackDays,
}: {
  run: BenchmarkRun | undefined;
  metric: Metric;
  compact: boolean;
  lookbackDays: number;
}) {
  if (!run) return <td className={styles.missing}>—</td>;
  const title = `${runTitle(run)}\n${historyTitle(run.history, lookbackDays)}`;

  if (metric === 'history') {
    const { history } = run;
    return (
      <td className={styles[historyStatus(history)]} title={title}>
        {compact
          ? formatNumber(history.average_score)
          : `avg ${formatNumber(history.average_score)} · ${history.passed}/${history.total} runs`}
      </td>
    );
  }

  const mark = run.passed ? '✓' : '✗';
  return (
    <td className={run.passed ? styles.pass : styles.fail} title={title}>
      {compact
        ? `${formatNumber(run.score)} ${mark}`
        : `${formatNumber(run.score)} / ${formatNumber(run.threshold)} ${mark}`}
      {!compact && run.series.length >= 2 && <Sparkline values={run.series} />}
    </td>
  );
}

function SkillRows({
  skill,
  models,
  lookbackDays,
  view,
}: {
  skill: BenchmarkSkill;
  models: string[];
  lookbackDays: number;
  view: BenchmarkView;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr>
        <th scope="row" className={styles.nameCol}>
          <button
            type="button"
            className={styles.toggle}
            aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}
          >
            <span className={styles.chevron} aria-hidden="true">▸</span>
            <span>{skill.name}</span>
            <span className={styles.count}>
              {skill.test_count} {skill.test_count === 1 ? 'test' : 'tests'}
            </span>
          </button>
        </th>
        <OverallCell
          summary={skill.overall}
          metric={view.metric}
          compact={view.compact}
          testCount={0}
          lookbackDays={lookbackDays}
          extraClass={styles.allCol}
        />
        {models.map((model) => (
          <SkillCell
            key={model}
            cell={skill.cells[model]}
            metric={view.metric}
            compact={view.compact}
            testCount={skill.test_count}
            lookbackDays={lookbackDays}
          />
        ))}
      </tr>
      {expanded &&
        skill.tests.map((test) => (
          <tr key={test.name} className={styles.testRow}>
            <th scope="row" className={styles.nameCol} title={test.name}>
              {testLabel(skill.name, test.name)}
            </th>
            <td className={styles.missing} />
            {models.map((model) => (
              <TestCell
                key={model}
                run={test.results[model]}
                metric={view.metric}
                compact={view.compact}
                lookbackDays={lookbackDays}
              />
            ))}
          </tr>
        ))}
    </>
  );
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
          <tr>
            <th scope="col" className={styles.nameCol}>Skill</th>
            <th scope="col" className={styles.allCol}>All models</th>
            {models.map((model) => (
              <th key={model} scope="col" title={model}>{model}</th>
            ))}
          </tr>
          <tr className={styles.overallRow}>
            <th scope="row" className={styles.nameCol}>
              Overall
              <span className={styles.count}>{testCount} tests</span>
            </th>
            <td className={styles.missing}>—</td>
            {models.map((model) => (
              <OverallCell
                key={model}
                summary={summary[model]}
                metric={view.metric}
                compact={view.compact}
                testCount={testCount}
                lookbackDays={lookbackDays}
              />
            ))}
          </tr>
        </thead>
        <tbody>
          {skills.map((skill) => (
            <SkillRows
              key={skill.name}
              skill={skill}
              models={models}
              lookbackDays={lookbackDays}
              view={view}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function testLabel(skill: string, test: string): string {
  return test.startsWith(`${skill}/`) ? test.slice(skill.length + 1) : test;
}
