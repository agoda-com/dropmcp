import styles from './ScreenshotGallery.module.css';

interface Props {
  urls: string[];
}

export default function ScreenshotGallery({ urls }: Props) {
  if (!urls.length) return null;
  return (
    <div className={styles.gallery}>
      {urls.map((url, i) => (
        <img key={i} src={url} alt={`Screenshot ${i + 1}`} loading="lazy" />
      ))}
    </div>
  );
}
