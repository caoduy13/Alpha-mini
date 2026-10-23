export function stripScheme(url: string): string {
  const t = url.trim();
  if (t.toLowerCase().startsWith('https://')) {
    return t.slice(8);
  }
  if (t.toLowerCase().startsWith('http://')) {
    return t.slice(7);
  }
  return t;
}

export function truncate(s: string, max = 160): string {
  const t = (s || '').trim();
  if (t.length <= max) {
    return t;
  }
  return `${t.slice(0, max - 1).trim()}…`;
}

export function isUrl(text: string): boolean {
  const t = text.trim().toLowerCase();
  return t.startsWith('http://') || t.startsWith('https://');
}
