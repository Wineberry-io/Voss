import { describe, expect, it } from 'vitest';
import { moveModeDirection } from '../moveMode';

describe('moveModeDirection', () => {
  it('maps hjkl, WASD, and arrows', () => {
    expect(moveModeDirection('h')).toBe('left');
    expect(moveModeDirection('j')).toBe('down');
    expect(moveModeDirection('k')).toBe('up');
    expect(moveModeDirection('l')).toBe('right');
    expect(moveModeDirection('W')).toBe('up');
    expect(moveModeDirection('a')).toBe('left');
    expect(moveModeDirection('S')).toBe('down');
    expect(moveModeDirection('d')).toBe('right');
    expect(moveModeDirection('ArrowRight')).toBe('right');
  });

  it('anything else exits the mode', () => {
    expect(moveModeDirection('Escape')).toBeNull();
    expect(moveModeDirection('x')).toBeNull();
    expect(moveModeDirection('Enter')).toBeNull();
  });
});
