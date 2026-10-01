import toolbarStyles from './FeedbackToolbar.module.css';

export default function Pill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={`${toolbarStyles.pill} ${active ? toolbarStyles.pillActive : ''}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
