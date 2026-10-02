import { useState } from 'react';
import { deleteMemory } from '../../api/memory';
import styles from './memory.module.css';

export default function MemoryDeleteButton({
  memoryKey,
  onDeleted,
}: {
  memoryKey: string;
  onDeleted: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirmDelete() {
    setError(null);
    try {
      await deleteMemory(memoryKey);
      onDeleted();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete memory.');
    }
  }

  return (
    <div className={styles.deleteRow}>
      {confirming ? (
        <>
          <p>Delete this memory?</p>
          <button type="button" className={styles.danger} onClick={confirmDelete}>
            Confirm delete
          </button>
          <button
            type="button"
            className={styles.secondary}
            onClick={() => setConfirming(false)}
          >
            Cancel
          </button>
        </>
      ) : (
        <button
          type="button"
          className={styles.danger}
          onClick={() => setConfirming(true)}
        >
          Delete
        </button>
      )}
      {error && <p className={styles.error}>{error}</p>}
    </div>
  );
}
