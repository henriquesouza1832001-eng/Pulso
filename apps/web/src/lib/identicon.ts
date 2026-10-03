/**
 * Identicons determinísticos (estilo GitHub): avatar geométrico colorido
 * por fonte de sinal. Imagem real sem depender de nada externo.
 */
const PALETTE = ["#34e07c", "#22d3ee", "#ffb340", "#7aa2ff", "#ff8a3d", "#ff5c6c", "#e3c05c"];
const cache = new Map<string, string>();

function hash(str: string): number {
	let h = 2166136261;
	for (let i = 0; i < str.length; i++) {
		h ^= str.charCodeAt(i);
		h = Math.imul(h, 16777619);
	}
	return h >>> 0;
}

export function identicon(seedStr: string, size = 24): string {
	const key = `${seedStr}:${size}`;
	const hit = cache.get(key);
	if (hit) return hit;

	let s = hash(seedStr) || 1;
	const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);

	const color = PALETTE[hash(seedStr) % PALETTE.length];
	const c = document.createElement("canvas");
	c.width = size;
	c.height = size;
	const g = c.getContext("2d")!;
	g.fillStyle = "#0b1119";
	g.fillRect(0, 0, size, size);

	const cell = size / 5;
	g.fillStyle = color;
	for (let x = 0; x < 3; x++)
		for (let y = 0; y < 5; y++) {
			if (rnd() > 0.45) {
				g.fillRect(x * cell, y * cell, cell - 0.5, cell - 0.5);
				g.fillRect((4 - x) * cell, y * cell, cell - 0.5, cell - 0.5);
			}
		}

	const url = c.toDataURL();
	cache.set(key, url);
	return url;
}
