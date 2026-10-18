export default [{
  ignores: ['**/vendor/**', '**/node_modules/**', '**/test-results/**'],
}, {
  files: ['**/*.js'],
  languageOptions: { ecmaVersion: 'latest', sourceType: 'module', globals: {
    process: 'readonly', Buffer: 'readonly', console: 'readonly', URL: 'readonly',
    setTimeout: 'readonly', clearTimeout: 'readonly', AbortController: 'readonly',
    structuredClone: 'readonly',
  } },
  rules: {
    'no-unused-vars': ['error', { argsIgnorePattern: '^_', caughtErrors: 'none' }],
    'no-unreachable': 'error', 'no-constant-condition': 'error', 'no-duplicate-imports': 'error',
    'no-dupe-keys': 'error', 'no-unsafe-finally': 'error', 'eqeqeq': 'error',
    'no-undef': 'error',
  },
}];
