"""Generate the animated "how it works" SVGs (light/dark × desktop/mobile).

    python docs/build_diagram.py

Pure CSS animation (no scripts), so GitHub renders it in a README <picture>.
Animation runs only under prefers-reduced-motion: no-preference; otherwise the
diagram is a static, numbered overview. This is an explanatory illustration;
the recorded demo (cookieguard-browser-use-demo.gif) shows a real run.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
DURATION = 12.0
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

THEMES = {
	'light': {'bg': '#FFFFFF', 'node': '#F6F8FA', 'stroke': '#D0D7DE', 'text': '#1F2328', 'muted': '#59636E',
		'line': '#AFB8C1', 'agent': '#0969DA', 'guard': '#8250DF', 'app': '#1A7F37', 'fail': '#CF222E',
		'warn': '#9A6700', 'glow': '#8250DF', 'chip': '#FFF8C5', 'failbg': '#FFEBE9'},
	'dark': {'bg': '#0D1117', 'node': '#161B22', 'stroke': '#30363D', 'text': '#E6EDF3', 'muted': '#9198A1',
		'line': '#3D444D', 'agent': '#4493F8', 'guard': '#AB7DF8', 'app': '#3FB950', 'fail': '#F85149',
		'warn': '#D29922', 'glow': '#AB7DF8', 'chip': '#2E2A1C', 'failbg': '#2D1517'},
}

NODES = {  # key: (title, subtitle, accent)
	'model': ('AI model', 'any provider', 'agent'),
	'agent': ('Browser Use agent', 'logs in, clicks, types', 'agent'),
	'chromium': ('Chromium', 'one browser session', 'muted'),
	'app': ('Your app', 'authorized test target', 'app'),
	'test': ('Your test code', 'start → run → finish', 'guard'),
	'engine': ('CookieGuard engine', 'local · CG001–CG009', 'guard'),
	'observer': ('CookieGuard observer', 'its own CDP connection', 'guard'),
}

# (start, end, caption, active nodes, comets as (edge, reverse))
STEPS = [
	(0.0, 1.6, 'Your test starts CookieGuard, then the Browser Use agent.', ['test'], []),
	(1.6, 3.6, 'The agent logs in. Its model sees the page, never cookie values.', ['model', 'agent', 'chromium'],
		[('c1', False), ('c2', False), ('c3', False)]),
	(3.6, 5.2, 'The app responds with Set-Cookie: session_id (here: no HttpOnly).', ['app'], [('c3', True)]),
	(5.2, 6.8, 'CookieGuard reads the same browser over its own CDP connection.', ['observer'], [('c4', False)]),
	(6.8, 8.4, 'The local engine applies the policy. Cookie values stay on your machine.', ['engine'], [('c5', False)]),
	(8.4, 11.2, 'Your test enforces the result. The agent cannot override it.', ['test'], [('c6', False)]),
]
STATIC_CAPTION = 'Test starts CookieGuard → agent logs in → app sets the cookie → CookieGuard observes → local engine decides → test enforces.'

LAYOUTS = {
	'desktop': {
		'size': (760, 340), 'node': (148, 62), 'font': 13, 'sub': 11, 'caption': 13, 'caption_y': 312, 'wrap': 200,
		'nodes': {'model': (16, 40), 'agent': (212, 40), 'chromium': (408, 40), 'app': (596, 40),
			'test': (16, 196), 'engine': (212, 196), 'observer': (408, 196)},
		'note': (596, 196),
		# Orthogonal polylines between node edges.
		'edges': {
			'c1': [(164, 71), (212, 71)], 'c2': [(360, 71), (408, 71)], 'c3': [(556, 71), (596, 71)],
			'c4': [(482, 102), (482, 196)], 'c5': [(408, 227), (360, 227)], 'c6': [(212, 227), (164, 227)],
			'tool': [(286, 102), (286, 196)],
		},
		'labels': {'c4': (498, 153, 'start'), 'tool': (294, 147, 'start')},
		'badges': {'test': (16, 196), 'c1': (188, 54), 'c3': (576, 54), 'c4': (482, 149), 'c5': (384, 211), 'c6': (188, 211)},
		'chips': {'setcookie': (558, 114), 'verdict': (16, 270)},
	},
	'mobile': {
		'size': (380, 560), 'node': (160, 58), 'font': 13, 'sub': 11, 'caption': 13, 'caption_y': 486, 'wrap': 44,
		'nodes': {'model': (14, 20), 'agent': (206, 20), 'app': (14, 130), 'chromium': (206, 130),
			'observer': (206, 240), 'test': (14, 350), 'engine': (206, 350)},
		'note': (14, 240),
		'edges': {
			'c1': [(174, 49), (206, 49)], 'c2': [(286, 78), (286, 130)], 'c3': [(206, 159), (174, 159)],
			'c4': [(286, 188), (286, 240)], 'c5': [(286, 298), (286, 350)], 'c6': [(206, 379), (174, 379)],
			'tool': [(366, 49), (374, 49), (374, 379), (366, 379)],
		},
		'labels': {},
		'badges': {'test': (14, 350), 'c1': (190, 33), 'c3': (190, 143), 'c4': (302, 214), 'c5': (302, 324), 'c6': (190, 363)},
		'chips': {'setcookie': (14, 194), 'verdict': (14, 422)},
	},
}
BADGE_STEP = {'test': 1, 'c1': 2, 'c3': 3, 'c4': 4, 'c5': 5, 'c6': 6}


def length(points):
	return sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(points, points[1:]))


def path(points):
	return 'M' + ' L'.join(f'{x},{y}' for x, y in points)


def pct(t):
	return f'{t / DURATION * 100:.2f}%'


def window_keyframes(name, start, end, on='1', off='0', prop='opacity'):
	a, b = pct(start), pct(end)
	return (f'@keyframes {name}{{0%,{pct(max(start - 0.01, 0))}{{{prop}:{off}}}{a},{b}{{{prop}:{on}}}'
		f'{pct(min(end + 0.01, DURATION))},100%{{{prop}:{off}}}}}')


def wrap(text, width):
	words, lines, current = text.split(), [], ''
	for word in words:
		if len(current) + len(word) + 1 > width and current:
			lines.append(current)
			current = word
		else:
			current = f'{current} {word}'.strip()
	return lines + [current]


def build(theme_name: str, layout_name: str) -> str:
	c, L = THEMES[theme_name], LAYOUTS[layout_name]
	W, H = L['size']
	nw, nh = L['node']
	css, body, animated = [], [], []
	css.append(f".t{{font-family:{FONT};fill:{c['text']}}}.m{{font-family:{MONO}}}.mu{{fill:{c['muted']}}}")
	css.append(f".edge{{stroke:{c['line']};stroke-width:1.5;fill:none}}.dash{{stroke-dasharray:4 4}}")
	css.append('.comet,.glow,.cap{opacity:0}.badge circle{transition:none}')
	css.append('@keyframes march{to{stroke-dashoffset:-16}}')
	body.append(f'<rect width="{W}" height="{H}" rx="12" fill="{c["bg"]}"/>')
	# Edges (static) and comets (animated pulses travelling along each edge).
	for key, points in L['edges'].items():
		cls = 'edge dash flow' if key == 'tool' else 'edge'
		body.append(f'<path class="{cls}" d="{path(points)}"/>')
		heads = [] if key == 'tool' else [(points[-1], points[-2])] + ([(points[0], points[1])] if key == 'c3' else [])
		for (x2, y2), (x1, y1) in heads:
			dx, dy = (x2 > x1) - (x2 < x1), (y2 > y1) - (y2 < y1)
			arrow = f'{x2},{y2} {x2 - 6 * dx - 4 * dy},{y2 - 6 * dy - 4 * dx} {x2 - 6 * dx + 4 * dy},{y2 - 6 * dy + 4 * dx}'
			body.append(f'<polygon points="{arrow}" fill="{c["line"]}"/>')
	if 'tool' in L['labels']:
		x, y, _ = L['labels']['tool']
		body.append(f'<text class="t mu" x="{x}" y="{y}" font-size="{L["sub"]}">optional read-only tool</text>')
		body.append(f'<text class="t mu m" x="{x}" y="{y + 14}" font-size="{L["sub"]}">cookieguard_audit</text>')
	if 'c4' in L['labels']:
		x, y, _ = L['labels']['c4']
		body.append(f'<text class="t mu" x="{x}" y="{y}" font-size="{L["sub"]}">separate CDP:</text>')
		body.append(f'<text class="t mu" x="{x}" y="{y + 14}" font-size="{L["sub"]}">Set-Cookie + cookie store</text>')
	for n, (start, end, _, _, comets) in enumerate(STEPS):
		slot = (end - start) / max(len(comets), 1)
		for i, (edge, reverse) in enumerate(comets):
			points = L['edges'][edge][::-1] if reverse else L['edges'][edge]
			total = length(points)
			a, b = start + i * slot, start + (i + 1) * slot
			name = f'k{n}{i}'
			color = c['warn'] if reverse else (c['agent'] if n == 1 else c['guard'])
			css.append(f'@keyframes {name}{{0%,{pct(a)}{{stroke-dashoffset:14;opacity:0}}{pct(a + 0.01)}{{opacity:1}}'
				f'{pct(b)}{{stroke-dashoffset:{-total};opacity:1}}{pct(b + 0.01)},100%{{stroke-dashoffset:{-total};opacity:0}}}}')
			body.append(f'<path class="comet" d="{path(points)}" stroke="{color}" stroke-width="3.5" stroke-linecap="round" '
				f'fill="none" stroke-dasharray="14 {total + 40}" style="animation-name:{name}"/>')
			animated.append(name)
	# Nodes, with an animated glow while each is active.
	for key, (x, y) in L['nodes'].items():
		title, subtitle, accent = NODES[key]
		color = c[accent] if accent != 'muted' else c['muted']
		body.append(f'<rect x="{x}" y="{y}" width="{nw}" height="{nh}" rx="10" fill="{c["node"]}" stroke="{c["stroke"]}"/>')
		body.append(f'<rect x="{x}" y="{y}" width="4" height="{nh}" rx="2" fill="{color}"/>')
		body.append(f'<text class="t" x="{x + 16}" y="{y + 26}" font-size="{L["font"]}" font-weight="600">{escape(title)}</text>')
		body.append(f'<text class="t mu" x="{x + 16}" y="{y + 44}" font-size="{L["sub"]}">{escape(subtitle)}</text>')
		windows = [(s, e) for s, e, _, nodes, _ in STEPS if key in nodes]
		for j, (s, e) in enumerate(windows):
			name = f'g{key}{j}'
			css.append(window_keyframes(name, s, e))
			body.append(f'<rect class="glow" x="{x - 3}" y="{y - 3}" width="{nw + 6}" height="{nh + 6}" rx="12" fill="none" '
				f'stroke="{c["glow"]}" stroke-width="2.5" style="animation-name:{name}"/>')
			animated.append(name)
	# Static note: where cookie values go.
	x, y = L['note']
	body.append(f'<rect x="{x}" y="{y}" width="{nw}" height="{nh}" rx="10" fill="none" stroke="{c["stroke"]}" stroke-dasharray="4 3"/>')
	for i, line in enumerate(['Cookie values: local', 'engine only. Never the', 'model, logs, or reports.']):
		body.append(f'<text class="t mu" x="{x + 12}" y="{y + 18 + i * 15}" font-size="{L["sub"]}">{line}</text>')
	# Numbered badges: always visible (static overview); pulse while their step runs.
	for key, (x, y) in L['badges'].items():
		number = BADGE_STEP[key]
		s, e = STEPS[number - 1][:2]
		name = f'b{number}'
		css.append(f'@keyframes {name}{{0%,{pct(s)}{{r:9}}{pct(s + 0.2)}{{r:12}}{pct(s + 0.5)},{pct(e)}{{r:10}}{pct(e + 0.2)},100%{{r:9}}}}')
		body.append(f'<g class="badge"><circle cx="{x}" cy="{y}" r="9" fill="{c["guard"]}" style="animation-name:{name}"/>'
			f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-size="11" font-weight="700" fill="{c["bg"]}" '
			f'font-family="{FONT}">{number}</text></g>')
		animated.append(name)
	# Chips: the Set-Cookie line and the verdict. Visible statically; timed when animated.
	x, y = L['chips']['setcookie']
	rows = ['Set-Cookie: session_id=…', 'Secure; SameSite=Lax']
	width = 7.2 * max(len(r) for r in rows) * (L['sub'] / 11) + 18
	texts = ''.join(f'<text class="t m" x="{x + 9}" y="{y + 16 + i * 15}" font-size="{L["sub"]}" style="fill:{c["warn"]}">'
		f'{escape(r)}</text>' for i, r in enumerate(rows))
	body.append(f'<g class="chip-set"><rect x="{x}" y="{y}" width="{width:.0f}" height="38" rx="6" fill="{c["chip"]}" '
		f'stroke="{c["warn"]}"/>{texts}</g>')
	css.append(f'@keyframes chipset{{0%,{pct(3.8)}{{opacity:0}}{pct(4.2)},{pct(11.6)}{{opacity:1}}{pct(11.9)},100%{{opacity:0}}}}')
	x, y = L['chips']['verdict']
	verdict = 'FAIL · CG001 Missing HttpOnly · exit 1'
	width = 7.4 * len(verdict) + 20
	body.append(f'<g class="chip-verdict"><rect x="{x}" y="{y}" width="{width:.0f}" height="24" rx="6" fill="{c["failbg"]}" '
		f'stroke="{c["fail"]}"/><text class="t" x="{x + 10}" y="{y + 16}" font-size="12" font-weight="700" '
		f'style="fill:{c["fail"]}">{escape(verdict)}</text></g>')
	css.append(f'@keyframes chipverdict{{0%,{pct(8.9)}{{opacity:0}}{pct(9.3)},{pct(11.6)}{{opacity:1}}{pct(11.9)},100%{{opacity:0}}}}')
	# Captions: one per step when animated; one summary line when static.
	cy = L['caption_y']
	for n, (start, end, caption, _, _) in enumerate(STEPS):
		name = f'c{n}'
		css.append(window_keyframes(name, start, end if n < len(STEPS) - 1 else DURATION - 0.3))
		lines = wrap(f'{n + 1}. {caption}', L['wrap'])
		tspans = ''.join(f'<tspan x="{W / 2}" dy="{0 if i == 0 else 17}">{escape(t)}</tspan>' for i, t in enumerate(lines))
		body.append(f'<text class="t cap" x="{W / 2}" y="{cy}" text-anchor="middle" font-size="{L["caption"]}" '
			f'style="animation-name:{name}">{tspans}</text>')
		animated.append(name)
	lines = wrap(STATIC_CAPTION, L['wrap'] if layout_name == 'mobile' else 120)
	tspans = ''.join(f'<tspan x="{W / 2}" dy="{0 if i == 0 else 16}">{escape(t)}</tspan>' for i, t in enumerate(lines))
	body.append(f'<text class="t mu static-cap" x="{W / 2}" y="{cy}" text-anchor="middle" font-size="{L["sub"] + 1}">{tspans}</text>')
	timing = f'{DURATION}s linear infinite'
	# Each element names its own keyframes inline; only timing is set here, so the
	# static (reduced-motion) diagram has no running animations at all.
	css.append('@media (prefers-reduced-motion:no-preference){'
		f'.comet,.glow,.cap,.badge circle{{animation-duration:{DURATION}s;animation-timing-function:linear;'
		'animation-iteration-count:infinite}'
		'.flow{animation:march 1s linear infinite}'
		f'.chip-set{{animation:chipset {timing}}}.chip-verdict{{animation:chipverdict {timing}}}.static-cap{{opacity:0}}}}')
	description = ('Animated overview of CookieGuard for Browser Use. ' + ' '.join(f'{i + 1}. {s[2]}' for i, s in enumerate(STEPS)))
	return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
		f'aria-labelledby="title desc"><title id="title">How CookieGuard for Browser Use works</title>'
		f'<desc id="desc">{escape(description)}</desc><style>{"".join(css)}</style>{"".join(body)}</svg>\n')


def main() -> None:
	for theme in THEMES:
		for layout in LAYOUTS:
			suffix = '' if layout == 'desktop' else '-mobile'
			(HERE / f'how-it-works-{theme}{suffix}.svg').write_text(build(theme, layout), encoding='utf-8')
			print(f'docs/how-it-works-{theme}{suffix}.svg')


if __name__ == '__main__':
	main()
