import type { PulsoEvent } from "@pulso/shared";
import { ago, CATEGORY_PT } from "../../lib/format";
import { LevelTag } from "../ui/LevelTag";

/** Briefings: análise curta editorial, sempre ligada às fontes e ao evento. */
export function Briefings({ events, onSelect }: { events: PulsoEvent[]; onSelect: (id: string) => void }) {
	const top = [...events].sort((a, b) => b.pulse - a.pulse).slice(0, 3);
	if (top.length === 0)
		return <p className="state">SEM BRIEFINGS · AGUARDANDO EVENTOS CONFIRMADOS</p>;

	return (
		<div className="briefs">
			{top.map((e) => (
				<article key={e.event_id} className="brief" onClick={() => onSelect(e.event_id)} role="button" tabIndex={0}>
					<span className="brief-kicker">
						{CATEGORY_PT[e.category]} · {[e.city, e.state].filter(Boolean).join("/").toUpperCase() || "LOCALIZANDO"} ·{" "}
						{ago(e.updated_at).toUpperCase()}
					</span>
					<h3>{e.title}</h3>
					<p>{e.summary ?? `${e.signal_count} sinais convergindo de ${e.source_count} fonte(s) independente(s).`}</p>
					<div className="brief-foot">
						<LevelTag level={e.alert_level} />
						<span className="dim">conf {e.confidence}% · sev {e.severity}</span>
						<span className="brief-cta">LER ANÁLISE →</span>
					</div>
				</article>
			))}
		</div>
	);
}
