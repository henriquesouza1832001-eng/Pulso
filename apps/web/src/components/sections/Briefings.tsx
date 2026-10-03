import { type CSSProperties, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { PulsoEvent } from "@pulso/shared";
import { ago, CATEGORY_PT } from "../../lib/format";
import { EventPeek } from "../events/EventPeek";
import { LevelTag } from "../ui/LevelTag";
import { Pager } from "../ui/Pager";

/**
 * Briefings: análise curta editorial, sempre ligada às fontes e ao evento.
 * Só eventos a partir de `minLevel`, do mais quente ao mais frio, `pageSize` por página.
 */
export function Briefings({
	events,
	onDossier,
	pageSize = 3,
	minLevel = 1,
}: {
	events: PulsoEvent[];
	/** "ver dossiê completo" dentro do briefing aberto */
	onDossier: (id: string) => void;
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

	// Briefing = sanfona própria: clicar abre análise + fontes no cartão, clicar de novo (ou Esc, ou trocar de página) fecha.
	const [openId, setOpenId] = useState<string | null>(null);
	const open = top.some((e) => e.event_id === openId) ? openId : null; // saiu da página na recarga: fecha
	const toggle = (id: string) => setOpenId((o) => (o === id ? null : id));
	const goPage = (p: number) => {
		setOpenId(null);
		setPage(p);
	};
	useEffect(() => {
		const onKey = (ev: KeyboardEvent) => {
			if (ev.key === "Escape") setOpenId(null);
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, []);

	// No painel largo os cartões têm altura fixa (dividem a altura do feed): o resumo usa 2 linhas quando cabem e 1
	// quando não, para nunca cortar texto no meio da linha nem empurrar o rodapé para fora. Em altura livre, fica em 2.
	const box = useRef<HTMLDivElement>(null);
	const shownKey = top.map((e) => e.event_id).join(",");
	useLayoutEffect(() => {
		const el = box.current;
		if (!el) return;
		const fit = () => {
			for (const card of el.querySelectorAll<HTMLElement>(".brief")) {
				const p = card.querySelector<HTMLElement>(":scope > p");
				const h3 = card.querySelector<HTMLElement>(":scope > h3");
				if (card.classList.contains("open")) {
					h3?.style.removeProperty("-webkit-line-clamp"); // aberto: título inteiro
					continue;
				}
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
	}, [shownKey, open]);
	if (top.length === 0)
		return <p className="state">SEM BRIEFINGS · AGUARDANDO EVENTOS{minLevel > 1 ? ` DE NÍVEL ${minLevel}+` : " CONFIRMADOS"}</p>;

	return (
		<>
			<div
				className={`briefs${open ? " has-open" : ""}`}
				ref={box}
				style={{ "--brief-rows": pageSize } as CSSProperties}
			>
				{top.map((e) => {
					const isOpen = e.event_id === open;
					return (
						<article
							key={e.event_id}
							className={`brief${isOpen ? " open" : ""}`}
							onClick={() => toggle(e.event_id)}
							onKeyDown={(ev) => {
								if (ev.target === ev.currentTarget && (ev.key === "Enter" || ev.key === " ")) {
									ev.preventDefault();
									toggle(e.event_id);
								}
							}}
							role="button"
							tabIndex={0}
							aria-expanded={isOpen}
						>
							<span className="brief-kicker">
								{CATEGORY_PT[e.category]} · {[e.city, e.state].filter(Boolean).join("/").toUpperCase() || "LOCALIZANDO"} ·{" "}
								{ago(e.updated_at).toUpperCase()}
							</span>
							<h3>{e.title}</h3>
							{isOpen ? (
								<EventPeek event={e} onDossier={onDossier} />
							) : (
								<p>{e.summary ?? `${e.signal_count} sinais convergindo de ${e.source_count} fonte(s) independente(s).`}</p>
							)}
							<div className="brief-foot">
								{!isOpen && (
									<>
										<LevelTag level={e.alert_level} />
										<span className="dim">conf {e.confidence}% · sev {e.severity}</span>
									</>
								)}
								<span className="brief-cta">{isOpen ? "FECHAR ▴" : "LER ANÁLISE ▾"}</span>
							</div>
						</article>
					);
				})}
			</div>
			<Pager
				page={cur}
				pages={pages}
				onPage={goPage}
				pageSize={pageSize}
				total={list.length}
				label="páginas dos briefings"
				maxButtons={9}
			/>
		</>
	);
}
