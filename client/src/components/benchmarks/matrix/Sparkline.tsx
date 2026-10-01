import styles from './Sparkline.module.css';

const WIDTH = 56;
const HEIGHT = 14;

export default function Sparkline({ values }: { values: number[] }) {
  return (
    <svg
      className={styles.sparkline}
      width={WIDTH}
      height={HEIGHT}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      aria-hidden="true"
    >
      <polyline
        points={sparklinePoints(values)}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  );
}

function sparklinePoints(values: number[]): string {
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  return values
    .map((value, index) => {
      const x = 1 + (index / (values.length - 1)) * (WIDTH - 2);
      const y = HEIGHT - 1 - ((value - min) / span) * (HEIGHT - 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}
