import { useState, useEffect, useMemo } from 'react';
import { fetchTelemetry, type SkillTelemetryResult } from '../api/catalog';
import TestResultRow from './TestResultRow';
import styles from './TelemetryPanel.module.css';

interface TelemetryPanelProps {
  itemName: string;
}

function shortTestName(fullName: string): string {
  const slash = fullName.indexOf('/');
  return slash >= 0 ? fullName.substring(slash + 1) : fullName;
}

export default function TelemetryPanel({ itemName }: TelemetryPanelProps) {
  const [results, setResults] = useState<SkillTelemetryResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchTelemetry(itemName)
      .then((data) => setResults(data.results || []))
      .finally(() => setLoading(false));
  }, [itemName]);

  const groupedByTest = useMemo(() => {
    const groups = new Map<string, SkillTelemetryResult[]>();
    for (const r of results) {
      const key = r.test_name;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(r);
    }
    return groups;
  }, [results]);

  if (loading) {
    return (
      <div className={styles.panel}>
        <h2>E2E Test Results</h2>
        <div className={styles.loading}>Loading telemetry...</div>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className={styles.panel}>
        <h2>E2E Test Results</h2>
        <p className={styles.empty}>No E2E test results available yet.</p>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <h2>E2E Test Results</h2>
      {[...groupedByTest.entries()].map(([testName, testResults]) => (
        <div key={testName} className={styles.testGroup}>
          <h3 className={styles.testGroupTitle}>{shortTestName(testName)}</h3>
          <table className={styles.table}>
            <thead>
              <tr>
                <th></th>
                <th>Model</th>
                <th>Score</th>
                <th>Duration</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {testResults.map((r, i) => (
                <TestResultRow key={i} result={r} />
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
