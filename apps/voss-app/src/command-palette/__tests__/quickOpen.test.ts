import { describe, expect, it } from 'vitest';
import { buildQuickOpenItems, filterQuickItems, flattenFiles } from '../quickOpen';

describe('quick open files', () => {
  it('flattens list_dir entries into workspace-relative paths', () => {
    const files = flattenFiles([
      { name: 'src', is_dir: true, children: [{ name: 'a.ts', is_dir: false }, { name: 'sub', is_dir: true, children: [{ name: 'b.ts', is_dir: false }] }] },
      { name: 'README.md', is_dir: false },
    ]);
    expect(files).toEqual(['src/a.ts', 'src/sub/b.ts', 'README.md']);
  });

  it('lists files after layouts and recents with file: ids', () => {
    const items = buildQuickOpenItems(['default'], ['/p/x'], ['src/a.ts']);
    expect(items.map((i) => i.section)).toEqual(['Layouts', 'Recent Projects', 'Files']);
    expect(items[2]).toMatchObject({ id: 'file:src/a.ts', label: 'a.ts', secondary: 'src/a.ts', glyph: 'F' });
    expect(filterQuickItems(items, 'a.ts').map((i) => i.id)).toEqual(['file:src/a.ts']);
  });
});
