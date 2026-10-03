import { useState } from "react";
import type { HistoryEntry } from "../../lib/api";
import { History } from "./Forecasts";

/** Histórico real de picos/eventos, filtrado nas janelas selecionadas. */
export function HistorySection({
	entries,
	loading,
	error,
}: {
	entries: HistoryEntry[];
	loading: boolean;
	error: string | null;
}) {
	const [tab, setTab] = useState<"24h" | "7d" | "30d">("24h");
	const days = tab === "24h" ? 1 : tab === "7d" ? 7 : 30;
	const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
	const shown = entries.filter((entry) => Date.parse(entry.date) >= cutoff);

	return (
		<div>
			<div className="tabs">
				{(["24h", "7d", "30d"] as const).map((t) => (
					<button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
						{t.toUpperCase()}
					</button>
				))}
			</div>
			{loading && entries.length === 0 ? (
				<p className="state">CARREGANDO HISTÓRICO…</p>
			) : error && entries.length === 0 ? (
				<p className="state err">HISTÓRICO INDISPONÍVEL · {error}</p>
			) : shown.length === 0 ? (
				<p className="state">SEM REGISTROS DE NÍVEL ELEVADO NESTE PERÍODO</p>
			) : (
				<History entries={shown} />
			)}
			<a className="back-live" href="#feed">
				↑ VOLTAR AOS DADOS AO VIVO
			</a>
		</div>
	);
}
