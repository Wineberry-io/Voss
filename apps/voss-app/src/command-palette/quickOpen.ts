/**
 * A7-02 Task 1 — quick-open item builders for ⌘P palette mode (D-05).
 *
 * Converts saved layout names and recent project paths into palette rows
 * with `Layouts` and `Recent Projects` sections. No Tauri or Solid.
 */

export interface QuickOpenItem {
  id: string;
  label: string;
  section: 'Layouts' | 'Recent Projects' | 'Files';
  glyph: string;
  secondary?: string;
}

export interface DirEntryLike {
  name: string;
  is_dir: boolean;
  children?: DirEntryLike[];
}

/** Workspace-relative file paths from a `list_dir` result, depth first. */
export function flattenFiles(entries: readonly DirEntryLike[], prefix = ''): string[] {
  const out: string[] = [];
  for (const e of entries) {
    const path = prefix ? `${prefix}/${e.name}` : e.name;
    if (e.is_dir) out.push(...flattenFiles(e.children ?? [], path));
    else out.push(path);
  }
  return out;
}

export function buildQuickOpenItems(
  layouts: readonly string[],
  recents: readonly string[],
  files: readonly string[] = [],
): QuickOpenItem[] {
  const items: QuickOpenItem[] = [];
  for (const name of layouts) {
    items.push({
      id: `layout:${name}`,
      label: name,
      section: 'Layouts',
      glyph: 'L',
    });
  }
  for (const path of recents) {
    const name = path.split('/').pop() || path;
    items.push({
      id: `recent:${path}`,
      label: name,
      section: 'Recent Projects',
      glyph: 'R',
      secondary: path,
    });
  }
  for (const path of files) {
    items.push({
      id: `file:${path}`,
      label: path.split('/').pop() || path,
      section: 'Files',
      glyph: 'F',
      secondary: path,
    });
  }
  return items;
}

/** Simple case-insensitive filter for quick-open items. */
export function filterQuickItems(
  items: readonly QuickOpenItem[],
  query: string,
): QuickOpenItem[] {
  if (!query) return [...items];
  const q = query.toLowerCase();
  return items.filter(
    (item) =>
      item.label.toLowerCase().includes(q) ||
      (item.secondary?.toLowerCase().includes(q) ?? false),
  );
}
