import { useEffect, useState } from "react";
import type { PulsoEvent } from "@pulso/shared";
import type { EventDetail as EventDetailData, SignalRow } from "../../lib/api";
import { api } from "../../lib/api";
import { ago, CATEGORY_PT, STATUS_PT } from "../../lib/format";
import { DEMO_SIGNALS } from "../../data/demo";
import { Blocks } from "../ui/Blocks";
import { Icon, CAT_ICON, catColor } from "../ui/Icon";
import { LevelTag } from "../ui/LevelTag";

/** Transparência editorial: o evento, por que tem esse score, e os sinais que o sustentam. */
export function EventDetail({ event }: { event: PulsoEvent }) {
	const [detail, setDetail] = useState<EventDetailData | null>(null);
	const [err, setErr] = useState<string | null>(null);

	const isDemo = event.event_id.startsWith("demo-");

	useEffect(() => {
		let alive = true;
		setDetail(null);
		setErr(null);
		if (isDemo) return; // sinais fictícios renderizados localmente
		api
			.event(event.event_id)
			.then((d) => alive && setDetail(d))
			.catch((e) => alive && setErr(String(e)));
		return () => {
			alive = false;
		};
	}, [event.event_id, isDemo]);

	const demoSignals: SignalRow[] | null = isDemo
		? (DEMO_SIGNALS[event.event_id] ?? DEMO_SIGNALS.default).map((s, i) => ({
				signal_id: `demo-sig-${i}`,
				source_id: s.source,
				source_name: s.source,
				source_class: s.cls,
				timestamp: new Date(Date.now() - (i + 1) * 7 * 60_000).toISOString(),
				collected_at: new Date().toISOString(),
				title: s.title,
				url: null,
				category: event.category,
			}))
		: null;

	const signals = detail?.signals ?? demoSignals ?? null;

	return (
		<div className="evdetail">
			<p style={{ color: "var(--tx0)", fontWeight: 700, display: "flex", gap: 8, alignItems: "center" }}>
				<Icon name={CAT_ICON[event.category] ?? "activity"} size={14} color={catColor(event.category)} />
				{event.title}
			</p>
			<div className="rowline">
				<span className="k">NÍVEL</span>
				<span className="v">
					<LevelTag level={event.alert_level} />
				</span>
			</div>
			<div className="rowline">
				<span className="k">CATEGORIA / STATUS</span>
				<span className="v">
					{CATEGORY_PT[event.category]} · {STATUS_PT[event.status]}
				</span>
			</div>
			<div className="rowline">
				<span className="k">SEVERIDADE</span>
				<span className="v">
					<Blocks value={event.severity} total={15} color="var(--org)" /> {event.severity}
				</span>
			</div>
			<div className="rowline">
				<span className="k">CONFIANÇA</span>
				<span className="v">
					<Blocks value={event.confidence} total={15} color="var(--cyn)" /> {event.confidence}%
				</span>
			</div>
			<div className="rowline">
				<span className="k">LOCAL</span>
				<span className="v">
					{[event.city, event.state].filter(Boolean).join(" · ") || "localizando…"} ·{" "}
					{event.geo_precision?.toLowerCase() ?? "n/d"}
				</span>
			</div>
			<div className="rowline">
				<span className="k">DETECTADO</span>
				<span className="v">{ago(event.detected_at)}</span>
			</div>

			<p className="dim" style={{ margin: "10px 0 2px", fontSize: 11, letterSpacing: "0.12em" }}>
				POR QUE PULSO {event.pulse}?
			</p>
			<ul className="whylist">
				{event.score_breakdown.map((c) => (
					<li key={c.key}>
						<span className="p">+{c.points}</span> {c.label}
					</li>
				))}
			</ul>

			<p className="dim" style={{ margin: "10px 0 0", fontSize: 11, letterSpacing: "0.12em" }}>
				SINAIS ({event.signal_count}) · FONTES INDEPENDENTES ({event.source_count})
			</p>
			{err && !isDemo && <p className="state err">SINAIS INDISPONÍVEIS · {err}</p>}
			{!signals && !err && <p className="skel">carregando sinais ████████████░░░░</p>}
			{signals && (
				<div className="siglist">
					{signals.map((s) => (
						<div key={s.signal_id} className="sigrow" title={s.title}>
							<span className="t">{brTime(s.timestamp)}</span>
							<span className="s">{s.source_name}</span>
							<span className="x">{s.title}</span>
						</div>
					))}
				</div>
			)}
		</div>
	);
}

function brTime(iso: string): string {
	return new Date(iso).toLocaleTimeString("pt-BR", {
		timeZone: "America/Sao_Paulo",
		hour12: false,
	});
}
