import { useState } from "react";
import type { PulsoEvent } from "@pulso/shared";

const STATUS_PT: Record<PulsoEvent["status"], string> = {
	DETECTED: "DETECTADO",
	DEVELOPING: "EM DESENVOLVIMENTO",
	CONFIRMED: "CONFIRMADO",
	STABLE: "ESTÁVEL",
	RESOLVING: "RESOLVENDO",
	RESOLVED: "RESOLVIDO",
	DISPUTED: "EM DISPUTA",
};

export function EventCard({ event: e }: { event: PulsoEvent }) {
	const [open, setOpen] = useState(false);
	return (
		<article className="panel">
			<p className="mono big">{e.pulse}</p>
			<h3>{e.title}</h3>
			<p className="mono dim">
				{[e.city, e.state].filter(Boolean).join(" — ")} · {STATUS_PT[e.status]}
			</p>
			{/* Severidade e confiança são medidas independentes. */}
			<p className="mono dim">
				SEVERIDADE {e.severity} · CONFIANÇA {e.confidence}% · {e.signal_count} sinais · {e.source_count} fontes
			</p>
			<button className="why" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
				POR QUE {e.pulse}?
			</button>
			{open && (
				<ul className="mono breakdown">
					{e.score_breakdown.map((c) => (
						<li key={c.key}>
							<span>+{c.points}</span> {c.label}
						</li>
					))}
				</ul>
			)}
		</article>
	);
}
