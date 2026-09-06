import { describe, expect, it } from 'vitest';
import { languageForPath } from '../editorLanguages';

describe('languageForPath', () => {
  it.each([
    ['src/a.ts', 'typescript'],
    ['src/a.tsx', 'typescript'],
    ['lib/b.js', 'javascript'],
    ['x.py', 'python'],
    ['main.rs', 'rust'],
    ['README.md', 'markdown'],
    ['package.json', 'json'],
    ['ci.yml', 'yaml'],
    ['Cargo.toml', 'toml'],
    ['Makefile', 'plain'],
    ['dir.with.dots/file', 'plain'],
  ])('%s → %s', (path, lang) => {
    expect(languageForPath(path)).toBe(lang);
  });
});
