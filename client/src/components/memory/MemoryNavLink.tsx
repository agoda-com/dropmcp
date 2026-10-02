import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

export default function MemoryNavLink() {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch('/catalog')
      .then((res) => (res.ok ? res.json() : null))
      .then((data: { memory_enabled?: boolean } | null) => {
        if (!cancelled && data?.memory_enabled) setEnabled(true);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  if (!enabled) return null;
  return (
    <>
      {' · '}
      <Link to="/memory">Memory</Link>
    </>
  );
}
