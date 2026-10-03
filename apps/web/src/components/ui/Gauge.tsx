import type { AlertLevel } from "@pulso/shared";

const LV_COLOR = ["", "#34e07c", "#ffb340", "#ff8a3d", "#ff4545", "#ff1744"];
const R = 92;
const CX = 120;
const CY = 118;

function polar(angleDeg: number, radius: number): [number, number] {
	const a = ((180 - angleDeg) * Math.PI) / 180;
	return [CX + radius * Math.cos(a), CY - radius * Math.sin(a)];
}

function arc(fromDeg: number, toDeg: number, radius: number): string {
	const [x1, y1] = polar(fromDeg, radius);
	const [x2, y2] = polar(toDeg, radius);
	return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${radius} ${radius} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
}

/**
 * Instrumento analógico nacional: 5 arcos de nível, ticks, agulha e leitura
 * digital com glow. No espírito do DOUGHCON do pizzint.
 */
export function Gauge({
	score,
	level,
	loading,
}: {
	score: number;
	level: AlertLevel;
	loading?: boolean;
}) {
	const angle = loading ? 0 : Math.max(0, Math.min(100, score)) * 1.8;
	const [nx, ny] = polar(angle, R - 16);
	const color = LV_COLOR[level] ?? LV_COLOR[1];

	return (
		<svg viewBox="0 0 240 148" className="gauge" role="img" aria-label={`pulso ${score} de 100, nível ${level}`}>
			{/* arcos de nível */}
			{[1, 2, 3, 4, 5].map((n) => {
				const from = (n - 1) * 36;
				const to = n * 36;
				const on = !loading && n === level;
				return (
					<g key={n}>
						<path d={arc(from, to, R)} stroke={LV_COLOR[n]} strokeWidth={on ? 10 : 4} opacity={on ? 1 : 0.28} fill="none" />
						{!loading && n === level && (
							<path d={arc(from, to, R)} stroke={LV_COLOR[n]} strokeWidth={10} opacity={0.25} fill="none" style={{ filter: "blur(4px)" }} />
						)}
					</g>
				);
			})}
			{/* ticks */}
			{Array.from({ length: 21 }, (_, i) => {
				const a = i * 9;
				const big = i % 5 === 0;
				const [x1, y1] = polar(a, R + 8);
				const [x2, y2] = polar(a, R + (big ? 15 : 12));
				return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#3d4a58" strokeWidth={big ? 1.4 : 1} />;
			})}
			{/* numerais */}
			{[0, 25, 50, 75, 100].map((v) => {
				const [x, y] = polar(v * 1.8, R + 26);
				return (
					<text key={v} x={x} y={y} textAnchor="middle" fill="#55616c" fontSize="9" fontFamily="JetBrains Mono, monospace">
						{v}
					</text>
				);
			})}
			{/* agulha */}
			{!loading && (
				<g>
					<line x1={CX} y1={CY} x2={nx} y2={ny} stroke="#e8eef4" strokeWidth="2.2" style={{ filter: `drop-shadow(0 0 4px ${color})` }} />
					<circle cx={CX} cy={CY} r="5" fill="#0b1119" stroke="#e8eef4" strokeWidth="1.6" />
					<circle cx={CX} cy={CY} r="1.8" fill={color} />
				</g>
			)}
			{/* leitura digital */}
			<text x={CX} y={CY - 34} textAnchor="middle" fill={loading ? "#3d4a58" : "#e8eef4"} fontSize="34" fontWeight="700" fontFamily="JetBrains Mono, monospace" style={loading ? undefined : { filter: `drop-shadow(0 0 8px ${color}66)` }}>
				{loading ? "--" : score}
			</text>
			<text x={CX} y={CY - 18} textAnchor="middle" fill={color} fontSize="10" letterSpacing="3" fontFamily="JetBrains Mono, monospace">
				{loading ? "SYNC" : `NÍVEL ${level}/100`}
			</text>
		</svg>
	);
}
