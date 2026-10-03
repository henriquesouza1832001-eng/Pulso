import { useMemo, useState } from "react";
import type { HealthSnapshot } from "../../lib/api";
import { ago } from "../../lib/format";

const ST_LABEL: Record<string, string> = {
	ONLINE: "ONLINE",
	DEGRADED: "DEGRADADA",
	RATE_LIMITED: "LIMITADA",
	OFFLINE: "OFFLINE",
	AUTH_ERROR: "ERRO AUTH",
	UNKNOWN: "DESCONHECIDA",
};

const ST_COLOR: Record<string, string> = {
	ONLINE: "var(--grn)",
	DEGRADED: "var(--amb)",
	RATE_LIMITED: "var(--amb)",
	OFFLINE: "var(--red)",
	AUTH_ERROR: "var(--red)",
	UNKNOWN: "var(--tx2)",
};

/**
 * Source monitor: saúde por fonte, direto do /api/health. Sensação OSINT sem inventar dado.
 * Com centenas de fontes, fica recolhido num resumo de uma linha; clicar expande a lista
 * (rolável, com busca e filtro), sempre com as fontes com problema primeiro.
 */
type Filter = "all" | "online" | "issues";

export function SourceMonitor({ health }: { health: HealthSnapshot | null }) {
	const [open, setOpen] = useState(false);
	const [query, setQuery] = useState("");
	const [filter, setFilter] = useState<Filter>("all");

	const sources = health?.sources ?? [];
	const online = sources.filter((s) => s.status === "ONLINE").length;
	const issues = sources.length - online;
	// "última coleta" = sucesso mais recente entre todas as fontes (não a primeira da lista).
	const lastSuccess = sources.reduce<string | null>(
		(acc, s) => (s.last_success && (!acc || s.last_success > acc) ? s.last_success : acc),
		null,
	);

	const shown = useMemo(() => {
		const q = query.trim().toLowerCase();
		return sources
			.filter((s) => (filter === "online" ? s.status === "ONLINE" : filter === "issues" ? s.status !== "ONLINE" : true))
			.filter((s) => !q || s.name.toLowerCase().includes(q))
			.sort((a, b) => Number(a.status === "ONLINE") - Number(b.status === "ONLINE") || a.name.localeCompare(b.name));
	}, [sources, query, filter]);

	if (!health) return <p className="state">CONECTANDO ÀS FONTES…</p>;
	if (sources.length === 0) return <p className="state">NENHUMA FONTE REGISTRADA · RODE O SEED</p>;

	const pct = Math.round((online / sources.length) * 100);

	return (
		<div className={`srcmon${open ? " open" : ""}`}>
			<button
				className="srcsum"
				onClick={() => setOpen((o) => !o)}
				aria-expanded={open}
				aria-controls="srcmon-list"
			>
				<span className="srcsum-txt">
					<b>{sources.length}</b> FONTES · <b style={{ color: "var(--grn)" }}>{online}</b> ONLINE
					{issues > 0 && (
						<>
							{" "}
							· <b style={{ color: "var(--red)" }}>{issues}</b> COM PROBLEMA
						</>
					)}
				</span>
				<span className="srcsum-caret" aria-hidden>
					{open ? "▴" : "▾"}
				</span>
				<span className="srcbar" aria-hidden>
					<i style={{ width: `${pct}%` }} />
				</span>
			</button>

			{open && (
				<div id="srcmon-list" className="srcdrop">
					<div className="srctools">
						<input
							type="search"
							value={query}
							onChange={(e) => setQuery(e.target.value)}
							placeholder="buscar fonte…"
							aria-label="buscar fonte pelo nome"
						/>
						<div className="srcfilt" role="group" aria-label="filtrar fontes por estado">
							{(
								[
									["all", `TODAS ${sources.length}`],
									["online", `ONLINE ${online}`],
									["issues", `PROBLEMA ${issues}`],
								] as const
							).map(([key, label]) => (
								<button key={key} className={filter === key ? "on" : ""} onClick={() => setFilter(key)}>
									{label}
								</button>
							))}
						</div>
					</div>
					<div className="srclist">
						{shown.map((s) => (
							<div key={s.source_id} className="srcrow" title={s.detail ?? undefined}>
								<span className="nm">{s.name.toUpperCase()}</span>
								<span className="fill" />
								<span className="ct" style={{ color: ST_COLOR[s.status] ?? "var(--tx2)" }}>
									● {ST_LABEL[s.status] ?? s.status}
								</span>
							</div>
						))}
						{shown.length === 0 && <p className="state">NENHUMA FONTE COM ESSE FILTRO</p>}
					</div>
				</div>
			)}

			<div className="srctotal">
				api {health.api.toLowerCase()} · db {health.db.toLowerCase()}
				{lastSuccess && <> · última coleta {ago(lastSuccess)}</>}
			</div>
		</div>
	);
}
