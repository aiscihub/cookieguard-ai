"""Generate the policy diagram SVGs (light/dark × desktop/mobile).

    python docs/build_policy_diagram.py

Shows how CookieGuardAudit options select which CookieGuard findings fail a
run. One gentle animation toggles fail_on between 'high' (default) and
'medium'; under prefers-reduced-motion the default state is shown statically.
Rule severities and option effects match @aiscihub/cookieguard-core 0.1.0.
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_diagram import FONT, MONO, THEMES  # noqa: E402

CYCLE = 10.0  # 0–5s fail_on='high', 5–10s fail_on='medium'

POLICY = [
	('CookieGuardAudit(', None),
	("  auth_cookies=['session_id'],", None),
	('  fail_on=', 'fail_on'),
	("  allowed_same_site=('lax','strict'),", None),
	('  require_host_only=False,', None),
	('  max_lifetime_days=30,', None),
	(')', None),
]
# (band, [(rule, title, hint, fails_when_medium)])
BANDS = [
	('high', [('CG001', 'Missing HttpOnly', None, True), ('CG002', 'Missing Secure', None, True),
		('CG006', 'Invalid cookie prefix', '__Host- / __Secure-', True), ('CG007', 'Protection regressed', 'finish(baseline=…)', True)]),
	('medium', [('CG003', 'SameSite outside policy', ('allowed_same_site', 'require_explicit_same_site'), True),
		('CG004', 'Domain sharing', 'review unless require_host_only=True', False),
		('CG005', 'Lifetime over the limit', 'max_lifetime_days', True)]),
	('review only · never fails', [('CG008', 'Role not confirmed', 'cookie not in auth_cookies', False),
		('CG009', 'Evidence needs review', 'e.g. SameSite declaration unknown', False)]),
]
RESULTS = [
	('FAIL · exit 1', 'fail', 'A confirmed finding at or above fail_on.'),
	('INCOMPLETE · exit 2', 'warn', 'An expected cookie is missing, or evidence is unreliable. Overrides FAIL.'),
	('PASS · exit 0', 'app', 'Otherwise. Review items may remain.'),
]
CAPTIONS = [
	"fail_on='high' (default): only high-severity findings fail the run.",
	"fail_on='medium': SameSite and lifetime findings fail too.",
]
STATIC_CAPTION = "With fail_on='medium', CG003 and CG005 fail too. CG004 fails only with require_host_only=True."

LAYOUTS = {
	'desktop': {'width': 760, 'policy': (16, 50, 266), 'rules': (298, 50, 282), 'results': (596, 50, 148), 'stack': False},
	'mobile': {'width': 380, 'policy': (14, 50, 352), 'rules': (14, 0, 352), 'results': (14, 0, 352), 'stack': True},
}


def wrap(text: str, width: int) -> list[str]:
	lines, current = [], ''
	for word in text.split():
		if current and len(current) + len(word) + 1 > width:
			lines.append(current)
			current = word
		else:
			current = f'{current} {word}'.strip()
	return lines + [current]


def keyframes(name: str, first: str, second: str, prop: str = 'opacity') -> str:
	"""Hold `first` for the first half of the cycle and `second` for the rest."""
	return f'@keyframes {name}{{0%,48%{{{prop}:{first}}}52%,98%{{{prop}:{second}}}100%{{{prop}:{first}}}}}'


def build(theme_name: str, layout_name: str) -> str:
	c, L = THEMES[theme_name], LAYOUTS[layout_name]
	W = L['width']
	css = [f".t{{font-family:{FONT};fill:{c['text']}}}.m{{font-family:{MONO}}}.mu{{fill:{c['muted']}}}",
		'.b,.cap{opacity:0}',
		keyframes('showA', '1', '0'), keyframes('showB', '0', '1'),
		'@media (prefers-reduced-motion:no-preference){'
		f'.a{{animation:showA {CYCLE}s linear infinite}}.b{{animation:showB {CYCLE}s linear infinite}}'
		f'.ca{{animation:showA {CYCLE}s linear infinite}}.cb{{animation:showB {CYCLE}s linear infinite}}.static{{opacity:0}}}}']
	body: list[str] = []
	body.append(f'<text class="t" x="16" y="30" font-size="15" font-weight="600">'
		'Your policy decides which findings fail the run</text>')

	# 1. Policy card.
	px, py, pw = L['policy']
	ph = 40 + len(POLICY) * 19 + 58
	body.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="10" fill="{c["node"]}" stroke="{c["stroke"]}"/>')
	body.append(f'<rect x="{px}" y="{py}" width="4" height="{ph}" rx="2" fill="{c["guard"]}"/>')
	body.append(f'<text class="t" x="{px + 16}" y="{py + 24}" font-size="13" font-weight="600">1 · Your policy</text>')
	for i, (line, dynamic) in enumerate(POLICY):
		y = py + 50 + i * 19
		indent = 13 if line.startswith('  ') else 0
		code = line.strip()
		body.append(f'<text class="t m" x="{px + 16 + indent}" y="{y}" font-size="11">{escape(code)}</text>')
		if dynamic:
			x = px + 16 + indent + len(code) * 6.62
			for cls, value in (('a', "'high',"), ('b', "'medium',")):
				body.append(f'<text class="t m {cls}" x="{x:.0f}" y="{y}" font-size="11" font-weight="700" '
					f'style="fill:{c["fail"]}">{escape(value)}</text>')
	note_y = py + 50 + len(POLICY) * 19 + 8
	for i, line in enumerate(wrap('Only cookies named in auth_cookies can be confirmed. Others are review items (CG008).',
			(pw - 32) // 6)):
		body.append(f'<text class="t mu" x="{px + 16}" y="{note_y + i * 15}" font-size="11">{escape(line)}</text>')

	# 2. Rules ladder, with the fail_on threshold drawn between bands.
	rx, ry, rw = L['rules']
	if L['stack']:
		ry = py + ph + 30
	body.append(f'<text class="t" x="{rx}" y="{ry + 14}" font-size="13" font-weight="600">2 · Rules by severity</text>')
	y = ry + 30
	threshold_y = {}
	for band, rules in BANDS:
		body.append(f'<text class="t mu" x="{rx}" y="{y + 10}" font-size="10" letter-spacing="0.6">{escape(band.upper())}</text>')
		y += 18
		for rule, title, hint, fails_medium in rules:
			hints = (hint,) if isinstance(hint, str) else (hint or ())
			h = 26 + 14 * len(hints)
			fails_high = band == 'high'
			body.append(f'<rect x="{rx}" y="{y}" width="{rw}" height="{h}" rx="7" fill="{c["node"]}" stroke="{c["stroke"]}"/>')
			if fails_high or fails_medium:
				cls = '' if fails_high else ' b'
				body.append(f'<rect class="{cls.strip()}" x="{rx}" y="{y}" width="{rw}" height="{h}" rx="7" '
					f'fill="{c["failbg"]}" stroke="{c["fail"]}"/>' if cls else
					f'<rect x="{rx}" y="{y}" width="{rw}" height="{h}" rx="7" fill="{c["failbg"]}" stroke="{c["fail"]}"/>')
			body.append(f'<text class="t m" x="{rx + 10}" y="{y + 17}" font-size="11" font-weight="700">{rule}</text>')
			body.append(f'<text class="t" x="{rx + 56}" y="{y + 17}" font-size="12">{escape(title)}</text>')
			for j, line in enumerate(hints):
				body.append(f'<text class="t mu m" x="{rx + 56}" y="{y + 32 + j * 13}" font-size="10">{escape(line)}</text>')
			label_x = rx + rw - 10
			if fails_high:
				body.append(f'<text class="t" x="{label_x}" y="{y + 17}" text-anchor="end" font-size="10" font-weight="700" '
					f'style="fill:{c["fail"]}">FAILS</text>')
			elif fails_medium:
				body.append(f'<text class="t mu a" x="{label_x}" y="{y + 17}" text-anchor="end" font-size="10">reported</text>')
				body.append(f'<text class="t b" x="{label_x}" y="{y + 17}" text-anchor="end" font-size="10" font-weight="700" '
					f'style="fill:{c["fail"]}">FAILS</text>')
			else:
				body.append(f'<text class="t mu" x="{label_x}" y="{y + 17}" text-anchor="end" font-size="10">reported</text>')
			y += h + 6
		threshold_y[band] = y + 6
		y += 22
	for cls, band, value in (('a', 'high', 'high'), ('b', 'medium', 'medium')):
		ty = threshold_y[band]
		body.append(f'<g class="{cls}"><line x1="{rx - 6}" y1="{ty}" x2="{rx + rw + 6}" y2="{ty}" stroke="{c["fail"]}" '
			f'stroke-width="2" stroke-dasharray="6 4"/><rect x="{rx + rw - 128}" y="{ty - 9}" width="122" height="18" rx="9" '
			f'fill="{c["bg"]}" stroke="{c["fail"]}"/><text class="t m" x="{rx + rw - 67}" y="{ty + 4}" text-anchor="middle" '
			f'font-size="10" font-weight="700" style="fill:{c["fail"]}">fail_on=\'{value}\' ▲</text></g>')
	rules_bottom = y

	# 3. Results.
	sx, sy, sw = L['results']
	if L['stack']:
		sy = rules_bottom + 16
	body.append(f'<text class="t" x="{sx}" y="{sy + 14}" font-size="13" font-weight="600">3 · Result</text>')
	y = sy + 30
	width_chars = (sw - 20) // 6
	for label, tone, text in RESULTS:
		lines = wrap(text, width_chars)
		h = 28 + len(lines) * 14
		body.append(f'<rect x="{sx}" y="{y}" width="{sw}" height="{h}" rx="8" fill="{c["node"]}" stroke="{c[tone]}"/>')
		body.append(f'<text class="t" x="{sx + 10}" y="{y + 18}" font-size="11" font-weight="700" style="fill:{c[tone]}">'
			f'{escape(label)}</text>')
		for i, line in enumerate(lines):
			body.append(f'<text class="t mu" x="{sx + 10}" y="{y + 34 + i * 14}" font-size="10.5">{escape(line)}</text>')
		y += h + 8
	bottom = max(rules_bottom, y, py + ph)

	# Captions: animated pair, or one static explanation.
	cy = bottom + 18
	wrap_at = 110 if not L['stack'] else 54
	for cls, caption in (('cap ca', CAPTIONS[0]), ('cap cb', CAPTIONS[1])):
		spans = ''.join(f'<tspan x="{W / 2}" dy="{0 if i == 0 else 16}">{escape(t)}</tspan>' for i, t in enumerate(wrap(caption, wrap_at)))
		body.append(f'<text class="t {cls}" x="{W / 2}" y="{cy}" text-anchor="middle" font-size="12.5">{spans}</text>')
	spans = ''.join(f'<tspan x="{W / 2}" dy="{0 if i == 0 else 16}">{escape(t)}</tspan>' for i, t in enumerate(wrap(STATIC_CAPTION, wrap_at)))
	body.append(f'<text class="t mu static" x="{W / 2}" y="{cy}" text-anchor="middle" font-size="12">{spans}</text>')
	H = cy + (40 if L['stack'] else 22)
	description = ('CookieGuard policy: CookieGuardAudit options decide which findings fail. High-severity rules CG001, CG002, '
		'CG006 and CG007 fail by default; medium rules CG003 and CG005 fail when fail_on is medium; CG004 needs '
		'require_host_only; CG008 and CG009 are review only. Results: FAIL, INCOMPLETE, or PASS.')
	return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
		f'aria-labelledby="title desc"><title id="title">CookieGuard policy</title><desc id="desc">{escape(description)}</desc>'
		f'<style>{"".join(css)}</style><rect width="{W}" height="{H}" rx="12" fill="{c["bg"]}"/>{"".join(body)}</svg>\n')


def main() -> None:
	for theme in THEMES:
		for layout in LAYOUTS:
			name = f'policy-{theme}{"" if layout == "desktop" else "-mobile"}.svg'
			(HERE / name).write_text(build(theme, layout), encoding='utf-8')
			print(f'docs/{name}')


if __name__ == '__main__':
	main()
