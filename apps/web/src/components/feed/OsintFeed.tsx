import { useEffect, useMemo, useRef, useState } from "react";
import type { PulsoEvent } from "@pulso/shared";
import { ago, brTime, CATEGORY_PT, evtId } from "../../lib/format";
import { identicon } from "../../lib/identicon";
import { LevelTag } from "../ui/LevelTag";

/**
 * Feed OSINT — timeline operacional densa no molde do pizzint:
 * avatar, hora Z, @fonte, texto, meta. Hairline entre itens, sem cards.
 * Tabs AO VIVO/TOP + filtro por categoria + rolagem infinita.
 */

const CAT_SOURCE: Record<string, string> = {
	EMERGENCY: "@bombeiros",
	TRAFFIC: "@prf_oficial",
	WEATHER: "@inmet",
	PROTEST: "@g1",
	SECURITY: "@ssp",
	INFRASTRUCTURE: "@onstatus",
};

const SRC_CLASS: Record<string, string> = {
	EMERGENCY: "OFICIAL",
	TRAFFIC: "OFICIAL",
	WEATHER: "OFICIAL",
	PROTEST: "NOTÍCIAS",
	SECURITY: "NOTÍCIAS",
	INFRASTRUCTURE: "OFICIAL",
};

function sourceFor(e: PulsoEvent, demo: boolean): string {
	if (!demo) return `agregado·${e.source_count}fontes`;
	return CAT_SOURCE[e.category] ?? "@pulso";
}

const PAGE = 14;

export function OsintFeed({
	events,
	onSelect,
	selectedId,
	demo,
	sourcesCount,
	onlineSources,
}: {
	events: PulsoEvent[];
	onSelect: (id: string) => void;
	selectedId: string | null;
	demo: boolean;
	sourcesCount: number;
	onlineSources: number;
}) {
	const [tab, setTab] = useState<"live" | "top">("live");
	const [cat, setCat] = useState<string>("ALL");
	const [visible, setVisible] = useState(PAGE);
	const listRef = useRef<HTMLDivElement>(null);
	const endRef = useRef<HTMLDivElement>(null);

	const cats = useMemo(() => {
		const present = new Map<string, number>();
		for (const e of events) present.set(e.category, (present.get(e.category) ?? 0) + 1);
		return [...present.entries()].sort((a, b) => b[1] - a[1]);
	}, [events]);

	const filtered = useMemo(() => {
		const list = cat === "ALL" ? [...events] : events.filter((e) => e.category === cat);
		if (tab === "top") list.sort((a, b) => b.pulse - a.pulse);
		else list.sort((a, b) => +new Date(b.updated_at) - +new Date(a.updated_at));
		return list;
	}, [events, cat, tab]);

	// troca de filtro/tab reinicia a paginação
	useEffect(() => {
		setVisible(PAGE);
	}, [cat, tab]);

	// rolagem infinita: sentinela no fim da lista
	useEffect(() => {
		const list = listRef.current;
		const end = endRef.current;
		if (!list || !end) return;
		const io = new IntersectionObserver(
			(entries) => {
				if (entries[0]?.isIntersecting) setVisible((v) => (v < filtered.length ? v + 10 : v));
			},
			{ root: list, rootMargin: "40px" },
		);
		io.observe(end);
		return () => io.disconnect();
	}, [filtered.length]);

	const reports = events.length;
	const alerts = events.filter((e) => e.alert_level >= 3).length;

	// faixa de atividade 24h (estilo timeline do pizzint): sinais por hora
	const hourBars = useMemo(() => {
		const bars = new Array(24).fill(0) as number[];
		const now = Date.now();
		for (const e of events) {
			const h = Math.floor((now - new Date(e.updated_at).getTime()) / 3_600_000);
			if (h >= 0 && h < 24) bars[23 - h] += e.signal_count;
		}
		return bars;
	}, [events]);
	const hourMax = Math.max(...hourBars, 1);
	const curHour = new Date()
		.toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo", hour12: false })
		.slice(0, 2);

	const shown = filtered.slice(0, visible);

	return (
		<div className="osf">
			<div className="osf-head">
				<span className="osf-title">
					<i className="dot-live" /> FEED OSINT
				</span>
				<span className="osf-meta dim">AUTO</span>
				<span className="osf-meta dim">MONITORANDO {sourcesCount || "--"} FONTES</span>
				<span className="osf-meta">
					{reports} RELATÓRIOS · <b className="l4">{alerts} ALERTAS</b>
				</span>
				<div className="osf-tabs">
					<button className={tab === "live" ? "on" : ""} onClick={() => setTab("live")}>
						AO VIVO
					</button>
					<button className={tab === "top" ? "on" : ""} onClick={() => setTab("top")}>
						TOP
					</button>
				</div>
			</div>

			<div className="osf-strip" aria-hidden>
				{hourBars.map((v, i) => (
					<i
						key={i}
						title={`${String(i).padStart(2, "0")}h · ${v} sinais`}
						style={{
							height: `${Math.max(8, (v / hourMax) * 100)}%`,
							background: v
								? String(i).padStart(2, "0") === curHour
									? "var(--red)"
									: "var(--acc)"
								: "var(--ln1)",
						}}
					/>
				))}
				<span className="oss-label">SINAIS/24H</span>
			</div>

			<div className="osf-cats" role="tablist" aria-label="filtrar por categoria">
				<button className={cat === "ALL" ? "on" : ""} onClick={() => setCat("ALL")}>
					TODAS · {events.length}
				</button>
				{cats.map(([c, n]) => (
					<button key={c} className={cat === c ? "on" : ""} onClick={() => setCat(c)}>
						{(CATEGORY_PT as Record<string, string>)[c] ?? c} · {n}
					</button>
				))}
			</div>

			{shown.length === 0 ? (
				<p className="state">AGUARDANDO COLETA · NENHUM RELATO COM ESSE FILTRO</p>
			) : (
				<div className="osf-list" ref={listRef}>
					{shown.map((e) => (
						<article
							key={e.event_id}
							className={`osf-item${e.event_id === selectedId ? " sel" : ""}`}
							onClick={() => onSelect(e.event_id)}
						>
							<img className="osf-avat" src={identicon(e.event_id, 20)} alt="" width={20} height={20} />
							<div className="osf-body">
								<div className="osf-line">
									<span className="osf-time">{brTime(e.updated_at)}</span>
									<span className="osf-src">{sourceFor(e, demo)}</span>
									{demo && <span className="osf-class">{SRC_CLASS[e.category] ?? "PUBLICO"}</span>}
									<span className="osf-id dim">{evtId(e.event_id)}</span>
									<span className="osf-ago dim">{ago(e.updated_at)}</span>
									<LevelTag level={e.alert_level} compact />
								</div>
								<p className="osf-text">{e.title}</p>
								<div className="osf-meta2">
									{e.signal_count} sinais · {e.source_count} fonte(s) · conf {e.confidence}% ·{" "}
									{[e.city, e.state].filter(Boolean).join("/") || "localizando…"}
								</div>
							</div>
						</article>
					))}
					<div ref={endRef} className="osf-more dim">
						{visible < filtered.length
							? `CARREGANDO MAIS… (${visible}/${filtered.length})`
							: `FIM · ${filtered.length} RELATOS CARREGADOS`}
					</div>
				</div>
			)}
			<p className="osf-foot dim">
				relatos brutos de fontes públicas, agregados pelo motor · clique para abrir o dossiê ·{" "}
				{onlineSources || "--"} fontes online agora
			</p>
		</div>
	);
}
