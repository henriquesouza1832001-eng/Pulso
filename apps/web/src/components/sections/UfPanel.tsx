import type { PulsoEvent } from "@pulso/shared";
import { ago, brTime, CATEGORY_PT, evtId } from "../../lib/format";
import { LevelTag } from "../ui/LevelTag";

const UF_NAME: Record<string, string> = {
	AC: "ACRE", AL: "ALAGOAS", AP: "AMAPÁ", AM: "AMAZONAS", BA: "BAHIA", CE: "CEARÁ",
	DF: "DISTRITO FEDERAL", ES: "ESPÍRITO SANTO", GO: "GOIÁS", MA: "MARANHÃO", MT: "MATO GROSSO",
	MS: "MATO GROSSO DO SUL", MG: "MINAS GERAIS", PA: "PARÁ", PB: "PARAÍBA", PR: "PARANÁ",
	PE: "PERNAMBUCO", PI: "PIAUÍ", RJ: "RIO DE JANEIRO", RN: "RIO GRANDE DO NORTE",
	RS: "RIO GRANDE DO SUL", RO: "RONDÔNIA", RR: "RORAIMA", SC: "SANTA CATARINA",
	SP: "SÃO PAULO", SE: "SERGIPE", TO: "TOCANTINS",
};

/**
 * Drill-down de UF: clique num estado do mapa (ou na lista lateral) abre
 * o painel com TODOS os eventos da unidade da federação.
 */
export function UfPanel({
	uf,
	events,
	onSelect,
	onClose,
}: {
	uf: string;
	events: PulsoEvent[];
	onSelect: (id: string) => void;
	onClose: () => void;
}) {
	const evs = events
		.filter((e) => e.state === uf)
		.sort((a, b) => b.pulse - a.pulse);
	const signals = evs.reduce((a, e) => a + e.signal_count, 0);
	const maxPulse = evs[0]?.pulse ?? 0;
	const level = evs.reduce((a, e) => Math.max(a, e.alert_level), 0);

	return (
		<div className="ufpanel">
			<div className="ufp-head">
				<span className="kicker">UNIDADE DA FEDERAÇÃO</span>
				<h3>
					{UF_NAME[uf] ?? uf} <span className="dim">· {uf}</span>
				</h3>
				<div className="ufp-stats">
					<span>
						<b>{evs.length}</b> eventos
					</span>
					<span>
						<b>{signals}</b> sinais
					</span>
					<span>
						pulso máx <b className={`l${level}`}>{maxPulse}</b>
					</span>
					<LevelTag level={level as 1} />
				</div>
				<button className="evclose" onClick={onClose} aria-label="fechar painel da UF">
					FECHAR ✕
				</button>
			</div>

			{evs.length === 0 ? (
				<p className="state">NENHUM EVENTO ATIVO NESTA UF AGORA</p>
			) : (
				<div className="ufp-list">
					{evs.map((e) => (
						<article key={e.event_id} className="ufp-row" onClick={() => onSelect(e.event_id)}>
							<span className="ufp-time dim">{brTime(e.updated_at)}</span>
							<LevelTag level={e.alert_level} compact />
							<span className="ufp-title">{e.title}</span>
							<span className="ufp-cat dim">{CATEGORY_PT[e.category]}</span>
							<span className="ufp-id dim">{evtId(e.event_id)}</span>
							<span className="ufp-meta dim">
								{e.signal_count}s · {e.source_count}f · conf {e.confidence}% · {ago(e.updated_at)}
							</span>
						</article>
					))}
				</div>
			)}
			<p className="ufp-foot dim">
				clique num evento para abrir o dossiê completo no feed · fonte: /api/events?state={uf}
			</p>
		</div>
	);
}
