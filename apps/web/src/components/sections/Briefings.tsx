import { type CSSProperties, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { PulsoEvent } from "@pulso/shared";
import { ago, CATEGORY_PT } from "../../lib/format";
import { LevelTag } from "../ui/LevelTag";

/**
 * Briefings: análise curta editorial, sempre ligada às fontes e ao evento.
 * Só eventos a partir de `minLevel`, do mais quente ao mais frio, `pageSize` por página.
 */
export function Briefings({
	events,
	onSelect,
	pageSize = 3,
	minLevel = 1,
}: {
	events: PulsoEvent[];
	onSelect: (id: string) => void;
	pageSize?: number;
	minLevel?: number;
}) {
	const list = useMemo(
		() => events.filter((e) => e.alert_level >= minLevel).sort((a, b) => b.pulse - a.pulse),
		[events, minLevel],
	);
	const [page, setPage] = useState(0);
	const pages = Math.max(1, Math.ceil(list.length / pageSize));
	const cur = Math.min(page, pages - 1); // a lista encolheu na recarga: fica na última página válida
	const top = list.slice(cur * pageSize, (cur + 1) * pageSize);

	// No painel largo os cartões têm altura fixa (dividem a altura do feed): o resumo usa 2 linhas quando cabem e 1
	// quando não, para nunca cortar texto no meio da linha nem empurrar o rodapé para fora. Em altura livre, fica em 2.
	const box = useRef<HTMLDivElement>(null);
	const shownKey = top.map((e) => e.event_id).join(",");
	useLayoutEffect(() => {
		const el = box.current;
		if (!el) return;
		const fit = () => {
			for (const card of el.querySelectorAll<HTMLElement>(".brief")) {
				const p = card.querySelector("p");
				const h3 = card.querySelector("h3");
				if (!p || !h3) continue;
				const over = () => card.scrollHeight > card.clientHeight + 1;
				p.style.setProperty("-webkit-line-clamp", "2");
				h3.style.removeProperty("-webkit-line-clamp");
				if (over()) p.style.setProperty("-webkit-line-clamp", "1");
				if (over()) h3.style.setProperty("-webkit-line-clamp", "1"); // aperto extremo: título também em 1 linha
			}
		};
		fit();
		if (typeof ResizeObserver === "undefined") return;
		const ro = new ResizeObserver(fit);
		ro.observe(el);
		return () => ro.disconnect();
	}, [shownKey]);
	if (top.length === 0)
		return <p className="state">SEM BRIEFINGS · AGUARDANDO EVENTOS{minLevel > 1 ? ` DE NÍVEL ${minLevel}+` : " CONFIRMADOS"}</p>;

	return (
		<>
			<div className="briefs" ref={box} style={{ "--brief-rows": pageSize } as CSSProperties}>
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
			{pages > 1 && (
				<nav className="osf-pages" aria-label="páginas dos briefings">
					<button disabled={cur === 0} onClick={() => setPage(cur - 1)} aria-label="página anterior">
						‹
					</button>
					<span className="osf-pgn">
						{cur + 1}/{pages}
					</span>
					<button disabled={cur === pages - 1} onClick={() => setPage(cur + 1)} aria-label="próxima página">
						›
					</button>
					<span className="dim">
						{cur * pageSize + 1}–{Math.min((cur + 1) * pageSize, list.length)} de {list.length}
					</span>
				</nav>
			)}
		</>
	);
}
