"""Check the Agent Skill's Python examples against the installed cookieguard_browser_use API.

Every ```python block in skills/cookieguard-browser-auth-security must parse (top-level
``await`` allowed), import only names the package exports, pass only keyword arguments
that ``CookieGuardAudit`` accepts, and use only methods and attributes that exist on
``CookieGuardAudit``, ``AuditResult``, and ``Finding``. Run with the integration's
virtualenv: ``.venv/bin/python scripts/check_skill_examples.py``. Exit 0 means every
example matches the code.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import re
import sys
from pathlib import Path

import cookieguard_browser_use as package
from cookieguard_browser_use import AuditResult, CookieGuardAudit, Finding

SKILL = Path(__file__).resolve().parents[3] / 'skills' / 'cookieguard-browser-auth-security'
BLOCK = re.compile(r'```python\n(.*?)```', re.S)


def members(cls) -> set[str]:
	names = {name for name in dir(cls) if not name.startswith('_')}
	if dataclasses.is_dataclass(cls):
		names |= {field.name for field in dataclasses.fields(cls) if not field.name.startswith('_')}
	return names


# Variables in the examples bound to each CookieGuard type.
TYPES = {'audit': members(CookieGuardAudit), 'result': members(AuditResult), 'finding': members(Finding)}
AUDIT_KWARGS = set(inspect.signature(CookieGuardAudit.__init__).parameters) - {'self'}


def check(source: str, origin: str) -> list[str]:
	errors = []
	tree = compile(source.replace('...', 'None'), origin, 'exec', flags=ast.PyCF_ONLY_AST | ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
	for node in ast.walk(tree):
		if isinstance(node, ast.ImportFrom) and node.module == 'cookieguard_browser_use':
			errors += [f'{origin}: {alias.name} is not exported' for alias in node.names if alias.name not in package.__all__]
		if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'CookieGuardAudit':
			errors += [f'{origin}: CookieGuardAudit has no {kw.arg}= argument' for kw in node.keywords if kw.arg not in AUDIT_KWARGS]
		if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in TYPES:
			if node.attr not in TYPES[node.value.id]:
				errors.append(f'{origin}: {node.value.id}.{node.attr} does not exist')
	return errors


def main() -> int:
	errors, blocks = [], 0
	for path in sorted(SKILL.rglob('*.md')):
		for index, match in enumerate(BLOCK.finditer(path.read_text())):
			blocks += 1
			errors += check(match.group(1), f'{path.relative_to(SKILL)}#{index + 1}')
	for error in errors:
		print(f'FAIL {error}')
	print(f'Checked {blocks} Python examples against cookieguard_browser_use {package.__version__}: '
		f'{"OK" if not errors else f"{len(errors)} problems"}')
	return 1 if errors or not blocks else 0


if __name__ == '__main__':
	sys.exit(main())
