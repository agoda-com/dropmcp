import DetailSection from './DetailSection';
import ScreenshotGallery from './ScreenshotGallery';

export default function ScreenshotsSection({ urls }: { urls: string[] }) {
  return (
    <DetailSection title="Screenshots">
      <ScreenshotGallery urls={urls} />
    </DetailSection>
  );
}
