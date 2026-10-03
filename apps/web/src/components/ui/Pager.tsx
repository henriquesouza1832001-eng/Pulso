/**
 * Paginação única do painel (feed, briefings, câmeras): ‹ 1 2 3 … › + "1–10 de 100".
 * Com mais páginas que `maxButtons`, mostra a primeira, a última e as vizinhas da atual, com "…" no meio.
 */
export function Pager({
	page,
	pages,
	onPage,
	pageSize,
	total,
	label,
	maxButtons = 10,
}: {
	page: number;
	pages: number;
	onPage: (p: number) => void;
	pageSize: number;
	total: number;
	label: string;
	maxButtons?: number;
}) {
	if (pages <= 1) return null;
	return (
		<nav className="osf-pages" aria-label={label}>
			<button disabled={page === 0} onClick={() => onPage(page - 1)} aria-label="página anterior">
				‹
			</button>
			{pageSlots(page, pages, maxButtons).map((p, i) =>
				p === null ? (
					<span key={`gap${i}`} className="osf-gap" aria-hidden>
						…
					</span>
				) : (
					<button
						key={p}
						className={p === page ? "on" : ""}
						aria-current={p === page ? "page" : undefined}
						onClick={() => onPage(p)}
					>
						{p + 1}
					</button>
				),
			)}
			<button disabled={page === pages - 1} onClick={() => onPage(page + 1)} aria-label="próxima página">
				›
			</button>
			<span className="dim">
				{page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} de {total}
			</span>
		</nav>
	);
}

/** Páginas a mostrar (base 0); null = "…". Sempre `max` posições quando há mais páginas que isso (a barra não pula). */
export function pageSlots(page: number, pages: number, max: number): (number | null)[] {
	const range = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, i) => from + i);
	if (pages <= max) return range(0, pages - 1);
	const inner = Math.max(1, max - 4); // primeira, última e os dois "…" ficam de fora
	const half = Math.floor(inner / 2);
	if (page <= half + 2) return [...range(0, max - 3), null, pages - 1]; // perto do começo
	if (page >= pages - 3 - half) return [0, null, ...range(pages - max + 2, pages - 1)]; // perto do fim
	const start = page - half;
	return [0, null, ...range(start, start + inner - 1), null, pages - 1];
}
