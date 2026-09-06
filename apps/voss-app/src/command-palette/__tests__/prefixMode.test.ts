import { describe, it, expect, vi } from 'vitest';
import { createPrefixMode } from '../prefixMode';

/**
 * A7-04 Task 1 — tmux prefix state machine tests.
 *
 * Verifies: profile gate, mapped keys, timeout, Esc cancel,
 * unknown key pass-through.
 */

function setup() {
  const onActivate = vi.fn();
  const onDeactivate = vi.fn();
  const dispatch = vi.fn();
  const timers = {
    setTimeout: vi.fn((_fn: () => void, _ms: number) => 42 as number),
    clearTimeout: vi.fn(),
  };

  const prefix = createPrefixMode({
    onActivate,
    onDeactivate,
    dispatch,
    setTimeout: timers.setTimeout,
    clearTimeout: timers.clearTimeout,
  });

  return { prefix, onActivate, onDeactivate, dispatch, timers };
}

describe('prefixMode — profile gate', () => {
  it('Cmd+B enters prefix only under tmux profile', () => {
    const { prefix, onActivate } = setup();
    expect(prefix.tryEnter('tmux')).toBe(true);
    expect(prefix.isActive()).toBe(true);
    expect(onActivate).toHaveBeenCalledTimes(1);
  });

  it('Cmd+B does not enter prefix under vscode profile', () => {
    const { prefix, onActivate } = setup();
    expect(prefix.tryEnter('vscode')).toBe(false);
    expect(prefix.isActive()).toBe(false);
    expect(onActivate).not.toHaveBeenCalled();
  });
});

describe('prefixMode — canvas keys', () => {
  it.each([
    ['m', 'canvas.moveMode'],
    ['z', 'canvas.zoomFit'],
    ['0', 'canvas.zoomReset'],
    ['f', 'canvas.zoomToFocused'],
  ])('%s dispatches %s', (key, commandId) => {
    const { prefix, dispatch } = setup();
    prefix.tryEnter('tmux');
    expect(prefix.handleKey(key)).toEqual({ action: 'consumed', commandId });
    expect(dispatch).toHaveBeenCalledWith(commandId);
  });
});

describe('prefixMode — mapped keys', () => {
  it('% dispatches pane.splitBelow and clears prefix', () => {
    const { prefix, dispatch } = setup();
    prefix.tryEnter('tmux');
    const result = prefix.handleKey('%');
    expect(result).toEqual({ action: 'consumed', commandId: 'pane.splitBelow' });
    expect(dispatch).toHaveBeenCalledWith('pane.splitBelow');
    expect(prefix.isActive()).toBe(false);
  });

  it('" dispatches pane.splitRight and clears prefix', () => {
    const { prefix, dispatch } = setup();
    prefix.tryEnter('tmux');
    const result = prefix.handleKey('"');
    expect(result).toEqual({ action: 'consumed', commandId: 'pane.splitRight' });
    expect(dispatch).toHaveBeenCalledWith('pane.splitRight');
  });

  it('o dispatches pane.focusNext', () => {
    const { prefix, dispatch } = setup();
    prefix.tryEnter('tmux');
    prefix.handleKey('o');
    expect(dispatch).toHaveBeenCalledWith('pane.focusNext');
  });

  it('x dispatches pane.close', () => {
    const { prefix, dispatch } = setup();
    prefix.tryEnter('tmux');
    prefix.handleKey('x');
    expect(dispatch).toHaveBeenCalledWith('pane.close');
  });

  it('c dispatches pane.splitRight (new pane)', () => {
    const { prefix, dispatch } = setup();
    prefix.tryEnter('tmux');
    prefix.handleKey('c');
    expect(dispatch).toHaveBeenCalledWith('pane.splitRight');
  });
});

describe('prefixMode — cancel behaviors', () => {
  it('Escape cancels prefix without dispatch', () => {
    const { prefix, dispatch, onDeactivate } = setup();
    prefix.tryEnter('tmux');
    const result = prefix.handleKey('Escape');
    expect(result).toEqual({ action: 'cancel' });
    expect(dispatch).not.toHaveBeenCalled();
    expect(prefix.isActive()).toBe(false);
    expect(onDeactivate).toHaveBeenCalled();
  });

  it('unknown key cancels and returns passthrough', () => {
    const { prefix, dispatch } = setup();
    prefix.tryEnter('tmux');
    const result = prefix.handleKey('q');
    expect(result).toEqual({ action: 'passthrough', key: 'q' });
    expect(dispatch).not.toHaveBeenCalled();
    expect(prefix.isActive()).toBe(false);
  });

  it('timeout after 1500ms clears prefix', () => {
    const { prefix, timers, onDeactivate } = setup();
    prefix.tryEnter('tmux');
    expect(timers.setTimeout).toHaveBeenCalledWith(expect.any(Function), 1500);

    // Invoke the timeout callback
    const timeoutFn = timers.setTimeout.mock.calls[0][0] as () => void;
    timeoutFn();

    expect(prefix.isActive()).toBe(false);
    expect(onDeactivate).toHaveBeenCalled();
  });

  it('cancel() clears the timeout timer', () => {
    const { prefix, timers } = setup();
    prefix.tryEnter('tmux');
    prefix.cancel();
    expect(timers.clearTimeout).toHaveBeenCalledWith(42);
  });
});

describe('prefixMode — double press', () => {
  it('pressing Cmd+B twice cancels prefix', () => {
    const { prefix, onDeactivate } = setup();
    prefix.tryEnter('tmux');
    expect(prefix.isActive()).toBe(true);
    prefix.tryEnter('tmux');
    expect(prefix.isActive()).toBe(false);
    expect(onDeactivate).toHaveBeenCalled();
  });
});
