import { describe, expect, it } from 'vitest';
import { isTypingKey, lastLines } from '../lod';

function buffer(lines: string[]) {
  return {
    length: lines.length,
    getLine: (y: number) => ({ translateToString: () => lines[y] }),
  };
}

describe('lastLines', () => {
  it('returns the last three non-empty lines, oldest first', () => {
    expect(lastLines(buffer(['a', 'b', '', 'c', 'd', '', '']))).toEqual(['b', 'c', 'd']);
  });

  it('handles short buffers', () => {
    expect(lastLines(buffer(['only']))).toEqual(['only']);
    expect(lastLines(buffer([]))).toEqual([]);
  });
});

describe('isTypingKey', () => {
  it('accepts printable keys and Enter without modifiers', () => {
    expect(isTypingKey(new KeyboardEvent('keydown', { key: 'a' }))).toBe(true);
    expect(isTypingKey(new KeyboardEvent('keydown', { key: 'Enter' }))).toBe(true);
    expect(isTypingKey(new KeyboardEvent('keydown', { key: 'a', metaKey: true }))).toBe(false);
    expect(isTypingKey(new KeyboardEvent('keydown', { key: 'ArrowLeft' }))).toBe(false);
    expect(isTypingKey(new KeyboardEvent('keydown', { key: 'Escape' }))).toBe(false);
  });
});
