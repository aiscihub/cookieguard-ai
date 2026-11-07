export default [{
  ignores: ['**/vendor/**', '**/node_modules/**', '**/test-results/**', '**/.venv/**', '**/dist/**'],
}, {
  files: ['**/*.js', '**/*.mjs'],
  languageOptions: { ecmaVersion: 'latest', sourceType: 'module', globals: {
    process: 'readonly', Buffer: 'readonly', console: 'readonly', URL: 'readonly',
    setTimeout: 'readonly', clearTimeout: 'readonly', AbortController: 'readonly',
    structuredClone: 'readonly', AbortSignal: 'readonly', URLSearchParams: 'readonly',
  } },
  rules: {
    'no-unused-vars': ['error', { argsIgnorePattern: '^_', caughtErrors: 'none' }],
    'no-unreachable': 'error', 'no-constant-condition': 'error', 'no-duplicate-imports': 'error',
    'no-dupe-keys': 'error', 'no-unsafe-finally': 'error', 'eqeqeq': 'error',
    'no-undef': 'error',
  },
}];
