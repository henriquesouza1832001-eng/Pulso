import { useMemo } from "react";
import type { PulsoEvent } from "@pulso/shared";
import { Blocks } from "../ui/Blocks";
import { levelVar } from "../ui/LevelTag";

const UF_NAME: Record<string, string> = {
	AC: "ACRE", AL: "ALAGOAS", AP: "AMAPÁ", AM: "AMAZONAS", BA: "BAHIA", CE: "CEARÁ",
	DF: "DISTRITO FEDERAL", ES: "ESPÍRITO SANTO", GO: "GOIÁS", MA: "MARANHÃO", MT: "MATO GROSSO",
	MS: "MATO GROSSO DO SUL", MG: "MINAS GERAIS", PA: "PARÁ", PB: "PARAÍBA", PR: "PARANÁ",
	PE: "PERNAMBUCO", PI: "PIAUÍ", RJ: "RIO DE JANEIRO", RN: "RIO GRANDE DO NORTE",
	RS: "RIO GRANDE DO SUL", RO: "RONDÔNIA", RR: "RORAIMA", SC: "SANTA CATARINA",
	SP: "SÃO PAULO", SE: "SERGIPE", TO: "TOCANTINS",
};

/** Ranking de estados em lista editorial com dotted-leader, ao lado do mapa. */
export function StateList({
	events,
	onStateSelect,
}: {
	events: PulsoEvent[];
	onStateSelect: (uf: string) => void;
}) {
	const rows = useMemo(() => {
		const m = new Map<string, { count: number; level: number; pulse: number; worst: PulsoEvent }>();
		for (const e of events) {
			if (!e.state) continue;
			const cur = m.get(e.state);
			if (!cur) m.set(e.state, { count: 1, level: e.alert_level, pulse: e.pulse, worst: e });
			else {
				cur.count++;
				cur.level = Math.max(cur.level, e.alert_level);
				cur.pulse = Math.max(cur.pulse, e.pulse);
				if (e.pulse > cur.worst.pulse) cur.worst = e;
			}
		}
		return [...m.entries()].sort((a, b) => b[1].pulse - a[1].pulse).slice(0, 8);
	}, [events]);

	if (rows.length === 0) return <p className="state">NENHUM ESTADO COM SINAL ATIVO</p>;

	return (
		<div className="statelist">
			{rows.map(([uf, r]) => (
				<button key={uf} className="srow" onClick={() => onStateSelect(uf)}>
					<span className="s-uf">{uf}</span>
					<span className="s-name">{(UF_NAME[uf] ?? uf).toUpperCase()}</span>
					<span className="s-fill" />
					<Blocks value={Math.min(15, r.pulse / 7)} total={15} color={levelVar(r.level as 1)} />
					<span className="s-val" style={{ color: levelVar(r.level as 1) }}>
						{r.pulse}
					</span>
					<span className="s-cnt dim">
						N{r.level} · {r.count}EV
					</span>
				</button>
			))}
		</div>
	);
}
