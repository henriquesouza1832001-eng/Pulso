// simplifica o geojson de estados para o mockup (uso único de desenvolvimento)
import { readFileSync, writeFileSync } from "node:fs";

const raw = JSON.parse(readFileSync(process.argv[2], "utf8"));

function dp(points, tol) {
	if (points.length < 4) return points;
	const keep = new Array(points.length).fill(false);
	keep[0] = keep[points.length - 1] = true;
	const stack = [[0, points.length - 1]];
	while (stack.length) {
		const [a, b] = stack.pop();
		let maxD = 0, idx = -1;
		const [ax, ay] = points[a], [bx, by] = points[b];
		const dx = bx - ax, dy = by - ay;
		const len = Math.hypot(dx, dy) || 1e-12;
		for (let i = a + 1; i < b; i++) {
			const [px, py] = points[i];
			const d = Math.abs(dy * (px - ax) - dx * (py - ay)) / len;
			if (d > maxD) { maxD = d; idx = i; }
		}
		if (maxD > tol) {
			keep[idx] = true;
			stack.push([a, idx], [idx, b]);
		}
	}
	return points.filter((_, i) => keep[i]);
}

const TOL = 0.04; // graus
const states = [];
for (const f of raw.features) {
	const uf = f.properties.sigla || f.properties.name.slice(0, 2).toUpperCase();
	const rings = [];
	for (const poly of f.geometry.coordinates) {
		const outer0 = poly[0];
		// anéis geojson são fechados (primeiro == último); abre antes de simplificar
		const closed =
			outer0.length > 1 &&
			outer0[0][0] === outer0.at(-1)[0] &&
			outer0[0][1] === outer0.at(-1)[1];
		const outer = closed ? outer0.slice(0, -1) : outer0;
		const simp = dp(outer, TOL).map(([lon, lat]) => [
			Math.round(lon * 100) / 100,
			Math.round(lat * 100) / 100,
		]);
		if (simp.length >= 6) rings.push(simp);
	}
	// mantém apenas os 3 maiores anéis por estado (ilhas mínimas fora)
	rings.sort((x, y) => y.length - x.length);
	states.push({ uf, rings: rings.slice(0, 3) });
}

const out = JSON.stringify(states);
writeFileSync(process.argv[3], out);
const total = states.reduce((a, s) => a + s.rings.reduce((b, r) => b + r.length, 0), 0);
console.log(`estados: ${states.length}, pontos: ${total}, tamanho: ${(out.length / 1024).toFixed(1)} KB`);
