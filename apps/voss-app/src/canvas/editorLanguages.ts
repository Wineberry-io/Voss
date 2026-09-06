export type EditorLanguage =
  | 'markdown'
  | 'typescript'
  | 'javascript'
  | 'python'
  | 'rust'
  | 'json'
  | 'yaml'
  | 'toml'
  | 'plain';

const BY_EXT: Record<string, EditorLanguage> = {
  md: 'markdown',
  markdown: 'markdown',
  ts: 'typescript',
  tsx: 'typescript',
  mts: 'typescript',
  cts: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  mjs: 'javascript',
  cjs: 'javascript',
  py: 'python',
  pyi: 'python',
  rs: 'rust',
  json: 'json',
  jsonc: 'json',
  yaml: 'yaml',
  yml: 'yaml',
  toml: 'toml',
};

export function languageForPath(path: string): EditorLanguage {
  const name = path.split('/').pop() ?? path;
  const dot = name.lastIndexOf('.');
  if (dot < 0) return 'plain';
  return BY_EXT[name.slice(dot + 1).toLowerCase()] ?? 'plain';
}
