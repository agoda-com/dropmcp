import { useEffect, useRef, lazy, Suspense, useState } from 'react';
import { fetchResourceContent, type SkillResource } from '../api/catalog';
import { isMarkdownPath, fencedCodeBlock } from '../utils/languageFromPath';
import LoadingSpinner from './LoadingSpinner';
import styles from './ResourceModal.module.css';

const Markdown = lazy(() => import('./Markdown'));

interface ResourceModalProps {
  resource: SkillResource;
  onClose: () => void;
}

export default function ResourceModal({ resource, onClose }: ResourceModalProps) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setContent(null);
    fetchResourceContent(resource.url)
      .then(setContent)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [resource.url]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  const markdownContent = content
    ? isMarkdownPath(resource.path)
      ? content
      : fencedCodeBlock(content, resource.path)
    : '';

  return (
    <div
      className={styles.overlay}
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={dialogRef}
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="resource-modal-title"
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.header}>
          <h3 id="resource-modal-title" className={styles.title}>
            {resource.path}
          </h3>
          <button
            type="button"
            className={styles.close}
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </header>

        <div className={styles.body}>
          {loading && <LoadingSpinner label="Loading resource…" />}
          {!loading && error && <p className={styles.error}>{error}</p>}
          {!loading && content && (
            <Suspense fallback={<LoadingSpinner label="Rendering…" />}>
              <Markdown>{markdownContent}</Markdown>
            </Suspense>
          )}
        </div>
      </div>
    </div>
  );
}
