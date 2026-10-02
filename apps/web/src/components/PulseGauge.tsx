import { useEffect, useState } from "react";
import type { PulseSnapshot } from "@pulso/shared";

const LEVEL_COLORS = ["", "#3ddc84", "#ffd23f", "#ff8a1f", "#ff453a", "#ff1744"];

export function PulseGauge({ snapshot, updatedAt }: { snapshot: PulseSnapshot; updatedAt: number | null }) {
	const [now, setNow] = useState(Date.now());
	useEffect(() => {
		const id = setInterval(() => setNow(Date.now()), 1000);
		return () => clearInterval(id);
	}, []);
	const ago = updatedAt ? Math.max(0, Math.round((now - updatedAt) / 1000)) : null;
	const color = LEVEL_COLORS[snapshot.alert_level] ?? LEVEL_COLORS[1];
	const filled = Math.round(snapshot.score / 5);
	const d = snapshot.delta_2h;

	return (
		<section className="gauge" aria-label="Pulso Brasil">
			<p className="mono dim">PULSO BRASIL</p>
			<p className="score mono" style={{ color }}>
				{snapshot.score}
				<span className="dim"> / 100</span>
			</p>
			<p className="mono" aria-hidden style={{ color }}>
				{"█".repeat(filled)}
				<span className="line">{"░".repeat(20 - filled)}</span>
			</p>
			<p className="level" style={{ color }}>
				PULSO {snapshot.alert_level} — {snapshot.label}
			</p>
			{d !== null && (
				<p className="mono">
					{d >= 0 ? "↑" : "↓"} {Math.abs(d)} pontos em 2 horas
				</p>
			)}
			{snapshot.contributors.length > 0 && (
				<p className="mono dim">
					{snapshot.contributors.map((c) => `${c.scope} ${c.delta >= 0 ? "+" : ""}${c.delta}`).join(" · ")}
				</p>
			)}
			<p className="note dim">
				Mede atividade e sinais públicos detectados. Não é probabilidade de dano nem prova de fato.
				{ago !== null && ` Atualizado há ${ago}s.`}
			</p>
		</section>
	);
}
