import { useEffect, useRef, useState } from "react";
import type { Category } from "@pulso/shared";
import type { Clock } from "../../hooks/useClock";
import { CATEGORY_PT } from "../../lib/format";
import { Icon } from "../ui/Icon";
import { UF_LIST } from "./regions";

/** Itens de navegação: só seções que existem de verdade na página (âncoras). */
const NAV: Array<[string, string, string]> = [
	// o mapa abre o painel e previsão + sensores dividem a mesma linha de cards: um item para cada bloco
	["painel", "Visão geral e mapa", "pin"],
	["previsao", "Previsão e sensores", "trend"],
	["feed", "Eventos", "alert"],
	["cameras", "Câmeras", "cam"],
	["historico", "Histórico", "clock"],
	["faq", "Sobre o Pulso", "globe"],
];

export function Sidebar() {
	const [active, setActive] = useState("painel");
	return (
		<nav className="dsb" aria-label="seções do painel">
			<a className="dsb-logo" href="#painel" onClick={() => setActive("painel")}>
				<Icon name="activity" size={22} color="var(--red)" />
				<span>
					<b>PULSO</b>
					<small>BRASIL EM TEMPO REAL</small>
				</span>
			</a>
			<ul>
				{NAV.map(([id, label, icon]) => (
					<li key={id}>
						<a href={`#${id}`} className={active === id ? "on" : ""} onClick={() => setActive(id)}>
							<Icon name={icon} size={15} />
							<span>{label}</span>
						</a>
					</li>
				))}
			</ul>
		</nav>
	);
}

export interface Filters {
	query: string;
	uf: string | null;
	category: Category | null;
}

export function DashTopBar({
	clock,
	live,
	filters,
	onFilters,
	sourcesOnline,
	sourcesTotal,
}: {
	clock: Clock;
	live: boolean;
	filters: Filters;
	onFilters: (f: Filters) => void;
	sourcesOnline: number;
	sourcesTotal: number;
}) {
	const pct = sourcesTotal ? Math.round((sourcesOnline / sourcesTotal) * 100) : 0;
	// A barra é fixa no topo e quebra em mais linhas em tela estreita: publica a altura real em --dtb-h para os links
	// do menu pararem logo abaixo dela (scroll-margin-top), em vez de esconder o título da seção atrás dela.
	const bar = useRef<HTMLElement>(null);
	useEffect(() => {
		const el = bar.current;
		if (!el || typeof ResizeObserver === "undefined") return;
		const root = document.documentElement;
		const ro = new ResizeObserver(() => root.style.setProperty("--dtb-h", `${el.offsetHeight}px`));
		ro.observe(el);
		return () => ro.disconnect();
	}, []);
	return (
		<header className="dtb" ref={bar}>
			<label className="dtb-search">
				<Icon name="scan" size={15} />
				<input
					type="search"
					value={filters.query}
					onChange={(e) => onFilters({ ...filters, query: e.target.value })}
					placeholder="Buscar cidade, evento, estado… (ex.: alagamento BH, apagão, manifestação)"
					aria-label="buscar eventos"
				/>
			</label>
			<span className={`dtb-live${live ? "" : " off"}`}>
				<i /> {live ? "AO VIVO" : "COLETA ATRASADA"}
			</span>
			<span className="dtb-clock">
				<b>{clock.br}</b>
				<small>{clock.date} (BRT)</small>
			</span>
			<select
				value={filters.uf ?? ""}
				onChange={(e) => onFilters({ ...filters, uf: e.target.value || null })}
				aria-label="filtrar por estado"
			>
				<option value="">Todos os estados</option>
				{UF_LIST.map((uf) => (
					<option key={uf} value={uf}>
						{uf}
					</option>
				))}
				<option value="BR">Nacional / sem UF</option>
			</select>
			<select
				value={filters.category ?? ""}
				onChange={(e) => onFilters({ ...filters, category: (e.target.value || null) as Category | null })}
				aria-label="filtrar por categoria"
			>
				<option value="">Todas as categorias</option>
				{Object.entries(CATEGORY_PT).map(([k, v]) => (
					<option key={k} value={k}>
						{v.charAt(0) + v.slice(1).toLowerCase()}
					</option>
				))}
			</select>
			<a className="dtb-src" href="#sensores" title="saúde das fontes">
				<small>Fontes online</small>
				<b>
					<span className="grn">↑ {sourcesOnline}</span> / {sourcesTotal || "--"}
				</b>
				<span className="dtb-bar" aria-hidden>
					<i style={{ width: `${pct}%` }} />
				</span>
			</a>
		</header>
	);
}
