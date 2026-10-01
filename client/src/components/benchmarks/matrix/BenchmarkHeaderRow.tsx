import styles from './BenchmarkMatrix.module.css';

export default function BenchmarkHeaderRow({ models }: { models: string[] }) {
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
