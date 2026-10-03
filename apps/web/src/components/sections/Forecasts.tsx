import type { PulsoEvent } from "@pulso/shared";
import { brTime } from "../../lib/format";

export interface Forecast {
	q: string;
	yes: number;
	drivers: string;
}

export interface HistEntry {
	date: string;
	text: string;
	level: 3 | 4 | 5;
}

/** Sparkline determinística usada nos cards de mercado. */
export function Sparkline({ seed, trend }: { seed: number; trend: number }) {
	const points = Array.from({ length: 16 }, (_, i) => {
		const x = (seed * (i + 3) * 7919) % 1000;
		return x / 1000;
	}).map((v, i) => v * 0.5 + (i / 15) * (trend / 100) * 0.7);
	const max = Math.max(...points, 0.001);
	const min = Math.min(...points);
	const rng = max - min || 1;
	const w = 220;
	const h = 26;
	const d = points
		.map((p, i) => {
			const x = (i / (points.length - 1)) * w;
			const y = h - 3 - ((p - min) / rng) * (h - 6);
			return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
		})
		.join(" ");
	const up = trend >= 50;
	return (
		<svg viewBox={`0 0 ${w} ${h}`} className="spark" preserveAspectRatio="none" aria-hidden>
			<path d={`${d} L ${w} ${h} L 0 ${h} Z`} fill={up ? "rgba(59,164,255,0.08)" : "rgba(154,160,166,0.07)"} stroke="none" />
			<path d={d} fill="none" stroke={up ? "var(--acc)" : "var(--tx2)"} strokeWidth="1.2" />
			<circle cx={w} cy={h - 3 - ((points[points.length - 1] - min) / rng) * (h - 6)} r="2" fill={up ? "var(--acc)" : "var(--tx2)"} />
		</svg>
	);
}

/** Histórico: momentos de nível alto registrados + eventos resolvidos recentes. */
export function History({ entries, events }: { entries: HistEntry[]; events: PulsoEvent[] }) {
	const resolved = events
		.filter((e) => e.status === "RESOLVED" || e.status === "RESOLVING")
		.slice(0, 3);
	return (
		<div className="hist">
			{resolved.map((e) => (
				<div key={e.event_id} className="histrow">
					<span className="d dim">{brTime(e.updated_at).slice(0, 5)}</span>
					<span>
						{e.title.toUpperCase()} · <b className={`l${e.alert_level}`}>N{e.alert_level}</b> ·{" "}
						{[e.city, e.state].filter(Boolean).join("/")}
					</span>
				</div>
			))}
			{entries.map((h) => (
				<div key={h.date + h.text} className="histrow">
					<span className="d dim">{h.date}</span>
					<span>
						{h.text} · <b className={`l${h.level}`}>N{h.level}</b>
					</span>
				</div>
			))}
		</div>
	);
}
