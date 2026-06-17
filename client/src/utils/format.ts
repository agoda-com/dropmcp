export function formatName(kebab: string): string {
  return kebab
    .split('-')
    .map((w) => (w.length ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : ''))
    .join(' ');
}
