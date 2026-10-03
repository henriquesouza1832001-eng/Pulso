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

const PAGE = 10;
/** Nível a partir do qual o evento fica FIXO no topo, em todas as páginas (alertas). */
const PIN_LEVEL = 3;
const MAX_PINNED = 5;

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
	const [page, setPage] = useState(0);
	const listRef = useRef<HTMLDivElement>(null);
	const rootRef = useRef<HTMLDivElement>(null);

	const cats = useMemo(() => {
		const present = new Map<string, number>();
		for (const e of events) present.set(e.category, (present.get(e.category) ?? 0) + 1);
		return [...present.entries()].sort((a, b) => b[1] - a[1]);
	}, [events]);

	const filtered = useMemo(() => {
		const list = cat === "ALL" ? [...events] : events.filter((e) => e.category === cat);
		// Nível mais alto sempre primeiro; dentro do nível, AO VIVO = mais recente, TOP = maior Pulso.
		list.sort(
			(a, b) =>
				b.alert_level - a.alert_level ||
				(tab === "top"
					? b.pulse - a.pulse
					: +new Date(b.updated_at) - +new Date(a.updated_at) || b.pulse - a.pulse),
		);
		return list;
	}, [events, cat, tab]);

	// Destaques: alertas (nível ≥ 3) fixos acima da lista, visíveis em qualquer página.
	const pinned = useMemo(() => filtered.filter((e) => e.alert_level >= PIN_LEVEL).slice(0, MAX_PINNED), [filtered]);
	const rest = useMemo(() => {
		const ids = new Set(pinned.map((e) => e.event_id));
		return filtered.filter((e) => !ids.has(e.event_id));
	}, [filtered, pinned]);
	const pages = Math.max(1, Math.ceil(rest.length / PAGE));
	const curPage = Math.min(page, pages - 1); // a lista encolheu (atualização/filtro): fica na última página válida

	// página nova começa do topo da lista
	useEffect(() => {
		listRef.current?.scrollTo({ top: 0 });
	}, [curPage]);

	// troca de filtro/tab volta para a primeira página
	useEffect(() => {
		setPage(0);
	}, [cat, tab]);

	// Evento escolhido no mapa/cidades/painel de UF: garante que ele apareça no feed (tira o filtro
	// de categoria que o esconda, carrega a página onde ele está) e rola a lista até ele.
	// Só uma vez por seleção: a atualização a cada 15 s ou um filtro escolhido depois não puxam a lista de volta.
	const pendingReveal = useRef<string | null>(null);
	useEffect(() => {
		pendingReveal.current = selectedId;
	}, [selectedId]);
	useEffect(() => {
		if (!selectedId || pendingReveal.current !== selectedId) return;
		if (cat !== "ALL" && !filtered.some((e) => e.event_id === selectedId)) {
			setCat("ALL");
			return; // reexecuta com a lista sem filtro
		}
		const idx = rest.findIndex((e) => e.event_id === selectedId);
		const target = idx < 0 ? curPage : Math.floor(idx / PAGE); // fixo nos destaques: qualquer página serve
		if (idx < 0 && !pinned.some((e) => e.event_id === selectedId)) return;
		if (target !== curPage) {
			setPage(target);
			return; // reexecuta depois de renderizar a página do item
		}
		pendingReveal.current = null;
		rootRef.current
			?.querySelector(`[data-evid="${CSS.escape(selectedId)}"]`)
			?.scrollIntoView({ behavior: "smooth", block: "nearest" });
	}, [selectedId, filtered, rest, pinned, cat, curPage]);


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

	const renderItem = (e: PulsoEvent) => (
		<article
			key={e.event_id}
			data-evid={e.event_id}
			className={`osf-item${e.alert_level >= 2 ? ` hot n${e.alert_level}` : ""}${e.event_id === selectedId ? " sel" : ""}`}
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
	);

	const shown = rest.slice(curPage * PAGE, (curPage + 1) * PAGE);

	return (
		<div className="osf" ref={rootRef}>
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

			{pinned.length > 0 && (
				<div className="osf-pin" aria-label="destaques: alertas de nível 3 ou mais">
					<span className="osf-pin-h">EM DESTAQUE · NÍVEL {PIN_LEVEL}+</span>
					{pinned.map(renderItem)}
				</div>
			)}

			{shown.length === 0 && pinned.length === 0 ? (
				<p className="state">AGUARDANDO COLETA · NENHUM RELATO COM ESSE FILTRO</p>
			) : (
				<div className="osf-list" ref={listRef}>
					{shown.map(renderItem)}
				</div>
			)}
			{pages > 1 && (
				<nav className="osf-pages" aria-label="páginas do feed">
					<button disabled={curPage === 0} onClick={() => setPage(curPage - 1)} aria-label="página anterior">
						‹
					</button>
					{Array.from({ length: pages }, (_, i) => (
						<button
							key={i}
							className={i === curPage ? "on" : ""}
							aria-current={i === curPage ? "page" : undefined}
							onClick={() => setPage(i)}
						>
							{i + 1}
						</button>
					))}
					<button disabled={curPage === pages - 1} onClick={() => setPage(curPage + 1)} aria-label="próxima página">
						›
					</button>
					<span className="dim">
						{curPage * PAGE + 1}–{Math.min((curPage + 1) * PAGE, rest.length)} de {rest.length}
					</span>
				</nav>
			)}
			<p className="osf-foot dim">
				relatos brutos de fontes públicas, agregados pelo motor · clique para abrir o dossiê ·{" "}
				{onlineSources || "--"} fontes online agora
			</p>
		</div>
	);
}
