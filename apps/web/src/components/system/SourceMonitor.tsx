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

/** Source monitor: saúde por fonte, direto do /api/health. Sensação OSINT sem inventar dado. */
export function SourceMonitor({ health }: { health: HealthSnapshot | null }) {
	if (!health) return <p className="state">CONECTANDO ÀS FONTES…</p>;

	const online = health.sources.filter((s) => s.status === "ONLINE").length;

	return (
		<div>
			{health.sources.map((s) => (
				<div key={s.source_id} className="srcrow" title={s.detail ?? undefined}>
					<span className="nm">{s.name.toUpperCase()}</span>
					<span className="fill" />
					<span className="ct" style={{ color: ST_COLOR[s.status] ?? "var(--tx2)" }}>
						● {ST_LABEL[s.status] ?? s.status}
					</span>
				</div>
			))}
			{health.sources.length === 0 && (
				<p className="state">NENHUMA FONTE REGISTRADA · RODE O SEED</p>
			)}
			<div className="srctotal">
				<b>{online}</b>/{health.sources.length} online · api {health.api.toLowerCase()} · db{" "}
				{health.db.toLowerCase()}
				{health.sources[0]?.last_success && (
					<> · última coleta {ago(health.sources[0].last_success)}</>
				)}
			</div>
		</div>
	);
}
