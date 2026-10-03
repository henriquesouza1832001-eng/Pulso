import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CameraFeed } from "@pulso/shared";
import { fold } from "../../lib/text";

const UF_NAME: Record<string, string> = {
	AC: "acre", AL: "alagoas", AP: "amapa", AM: "amazonas", BA: "bahia", CE: "ceara", DF: "distrito federal",
	ES: "espirito santo", GO: "goias", MA: "maranhao", MT: "mato grosso", MS: "mato grosso do sul", MG: "minas gerais",
	PA: "para", PB: "paraiba", PR: "parana", PE: "pernambuco", PI: "piaui", RJ: "rio de janeiro",
	RN: "rio grande do norte", RS: "rio grande do sul", RO: "rondonia", RR: "roraima", SC: "santa catarina",
	SP: "sao paulo", SE: "sergipe", TO: "tocantins",
};

/** Apelidos comuns de cidade na busca ("alagamento BH"). */
const CITY_ALIAS: Record<string, string> = {
	bh: "belo horizonte",
	poa: "porto alegre",
	bsb: "brasilia",
	ssa: "salvador",
	sampa: "sao paulo",
	floripa: "florianopolis",
	cwb: "curitiba",
};

/**
 * Lê a busca do topo do painel como LUGAR: cidade citada (inteira, ou começo dela enquanto digita), nome de estado ou
 * sigla de UF escrita em maiúsculas ("SE" e "TO" também são palavras). Usa o recorte mais específico que achar
 * (cidade > estado > texto parcial). Devolve null quando a busca não cita nenhum lugar com câmera: aí ela não recorta.
 */
function placeFilter(query: string, feeds: CameraFeed[]): ((c: CameraFeed) => boolean) | null {
	const q = fold(query).trim().replace(/[^a-z0-9]+/g, " ");
	if (q.length < 2) return null;
	const words = q.split(" ");
	const text = ` ${words.map((w) => CITY_ALIAS[w] ?? w).join(" ")} `;
	const codes = new Set(
		query
			.split(/[^A-Za-z]+/)
			.filter((w) => w.length === 2 && (w === w.toUpperCase() || words.length === 1))
			.map((w) => w.toUpperCase()),
	);
	const byCity = (c: CameraFeed) => {
		const city = fold(c.city);
		return city.length >= 3 && text.includes(` ${city} `);
	};
	const byState = (c: CameraFeed) => codes.has(c.state) || (!!UF_NAME[c.state] && text.includes(` ${UF_NAME[c.state]} `));
	const partial = (c: CameraFeed) => q.length >= 3 && (fold(c.city).startsWith(q) || fold(c.label).includes(q));
	return [byCity, byState, partial].find((f) => feeds.some(f)) ?? null;
}

/** Ordem FIXA (com prévia primeiro, depois UF, cidade e nome): a lista nunca se reembaralha quando o catálogo é rebaixado. */
function sortFeeds(feeds: CameraFeed[]): CameraFeed[] {
	return [...feeds].sort(
		(a, b) =>
			Number(b.preview !== null) - Number(a.preview !== null) ||
			a.state.localeCompare(b.state) ||
			a.city.localeCompare(b.city, "pt-BR") ||
			a.label.localeCompare(b.label, "pt-BR") ||
			a.id.localeCompare(b.id),
	);
}

function countBy(items: CameraFeed[], key: (c: CameraFeed) => string): [string, number][] {
	const m = new Map<string, number>();
	for (const c of items) m.set(key(c), (m.get(key(c)) ?? 0) + 1);
	return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0], "pt-BR"));
}

/**
 * Câmeras reais: recorte pela busca do topo (cidade/estado), filtro por estado e cidade + paginação.
 * Só os cartões da página atual existem (e ficam ativos).
 */
export function CameraFeeds({
	feeds,
	focusUf = null,
	query = "",
	pageSize = 12,
}: {
	feeds: CameraFeed[];
	focusUf?: string | null;
	query?: string;
	pageSize?: number;
}) {
	const PAGE = pageSize;
	const [uf, setUfRaw] = useState("");
	const [city, setCityRaw] = useState("");
	const [page, setPage] = useState(0);
	const sorted = useMemo(() => sortFeeds(feeds), [feeds]);
	const place = useMemo(() => placeFilter(query, sorted), [query, sorted]);
	const all = useMemo(() => (place ? sorted.filter(place) : sorted), [sorted, place]);
	const ufs = useMemo(() => countBy(all, (c) => c.state), [all]);
	const cities = useMemo(
		() =>
			uf && all.some((c) => c.state === uf)
				? countBy(
						all.filter((c) => c.state === uf),
						(c) => c.city,
					)
				: [],
		[all, uf],
	);
	// a busca pode tirar da lista o estado/cidade escolhidos: aí o seletor volta para "todos" sem apagar a escolha
	const ufOk = ufs.some(([u]) => u === uf) ? uf : "";
	const cityOk = cities.some(([c]) => c === city) ? city : "";
	const filtered = useMemo(
		() => all.filter((c) => (!ufOk || c.state === ufOk) && (!cityOk || c.city === cityOk)),
		[all, ufOk, cityOk],
	);
	const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
	const cur = Math.min(page, pages - 1); // a lista encolheu: fica na última página válida
	const shown = filtered.slice(cur * PAGE, (cur + 1) * PAGE);

	// Estado escolhido no topo do painel ou no mapa também recorta as câmeras (os seletores daqui refinam).
	// Reage à troca do estado em foco e ao catálogo ficar pronto (não a cada recarga, para não apagar a escolha manual).
	const ready = sorted.length > 0;
	useEffect(() => {
		setUfRaw(focusUf && sorted.some((c) => c.state === focusUf) ? focusUf : "");
		setCityRaw("");
		setPage(0);
	}, [focusUf, ready]); // eslint-disable-line react-hooks/exhaustive-deps
	// busca nova = recorte novo: volta para a primeira página
	useEffect(() => setPage(0), [query]);

	const setUf = (v: string) => {
		setUfRaw(v);
		setCityRaw("");
		setPage(0);
	};
	const setCity = (v: string) => {
		setCityRaw(v);
		setPage(0);
	};
	const reset = () => setUf("");

	return (
		<div className="camfeeds">
			<div className="osf-uf">
				<label>
					<span className="dim">ESTADO</span>
					<select
						value={ufOk}
						onChange={(e) => setUf(e.target.value)}
						aria-label="filtrar câmeras por estado"
					>
						<option value="">TODOS · {all.length}</option>
						{ufs.map(([u, n]) => (
							<option key={u} value={u}>
								{u === "BR" ? "NACIONAL" : u} · {n}
							</option>
						))}
					</select>
				</label>
				<label>
					<span className="dim">CIDADE</span>
					<select
						value={cityOk}
						disabled={!ufOk}
						onChange={(e) => setCity(e.target.value)}
						aria-label="filtrar câmeras por cidade"
					>
						<option value="">{ufOk ? `TODAS · ${all.filter((c) => c.state === ufOk).length}` : "escolha um estado"}</option>
						{cities.map(([c, n]) => (
							<option key={c} value={c}>
								{c.toUpperCase()} · {n}
							</option>
						))}
					</select>
				</label>
				{(ufOk || cityOk) && (
					<button className="osf-ufchip" onClick={reset}>
						LIMPAR ✕
					</button>
				)}
			</div>
			{place && (
				<p className="camq dim">
					BUSCA “{query.trim()}” · {all.length} CÂMERA{all.length === 1 ? "" : "S"}
				</p>
			)}
			{shown.length === 0 ? (
				<p className="state">NENHUMA CÂMERA NESTE FILTRO</p>
			) : (
				<div className="camgrid">
					{shown.map((f) => (
						<CameraFeedTile key={f.id} cam={f} />
					))}
				</div>
			)}
			{pages > 1 && (
				<nav className="osf-pages" aria-label="páginas das câmeras">
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
						{cur * PAGE + 1}–{Math.min((cur + 1) * PAGE, filtered.length)} de {filtered.length}
					</span>
				</nav>
			)}
		</div>
	);
}

/**
 * Câmera REAL de um provedor. O PULSO é só o placeholder: a prévia vem do player do próprio provedor (iframe ou HLS,
 * nunca retransmitida por nós) e o clique leva à página de origem.
 *
 * Contra o "piscar": o cartão é memoizado (o App re-renderiza a cada 10 s e o catálogo é rebaixado a cada 10 min sem mudar);
 * a prévia é montada UMA vez, quando o cartão chega perto da tela, e fica ativa (não desmonta ao rolar). O player HLS não
 * depende de callbacks que mudam a cada render e se reconecta sozinho. Só a página atual tem player.
 */
const CameraFeedTile = memo(
	function CameraFeedTile({ cam }: { cam: CameraFeed }) {
		const box = useRef<HTMLDivElement>(null);
		const [armed, setArmed] = useState(false);
		const [failed, setFailed] = useState(false);
		const [ready, setReady] = useState(false);
		const onFail = useCallback(() => setFailed(true), []);
		const onReady = useCallback(() => setReady(true), []);

		useEffect(() => {
			const el = box.current;
			if (!el || typeof IntersectionObserver === "undefined") {
				setArmed(true);
				return;
			}
			const io = new IntersectionObserver(
				([e]) => {
					if (e.isIntersecting) {
						setArmed(true);
						io.disconnect(); // uma vez armado, o player fica
					}
				},
				{ rootMargin: "300px" },
			);
			io.observe(el);
			return () => io.disconnect();
		}, []);

		const preview = cam.preview;
		const live = preview !== null && !failed;
		return (
			<div className="camtile">
				<div className={`camview${live && ready ? " ready" : ""}`} ref={box}>
					<div className="camph">
						<span>{cam.provider.toUpperCase()}</span>
						<span className="dim">{live ? (armed ? "conectando…" : "") : "ver ao vivo no site de origem"}</span>
					</div>
					{live && armed && preview.type === "iframe" && (
						<iframe src={preview.url} title={cam.label} sandbox="allow-scripts allow-same-origin" tabIndex={-1} onLoad={onReady} />
					)}
					{live && armed && preview.type === "hls" && <HlsVideo src={preview.url} onFail={onFail} onReady={onReady} />}
					<a
						className="camlink"
						href={cam.page_url}
						target="_blank"
						rel="noopener noreferrer"
						aria-label={`Abrir ${cam.label} em ${cam.provider}`}
					>
						<span>ver no site ↗</span>
					</a>
				</div>
				<div className="caminfo">
					<span className="nm">{cam.label.toUpperCase()}</span>
					<span className="loc dim">
						{cam.city.toUpperCase()} · {cam.state}
					</span>
					<span className="st dim">{cam.attribution}</span>
				</div>
			</div>
		);
	},
	(a, b) => a.cam.id === b.cam.id && a.cam.page_url === b.cam.page_url && a.cam.preview?.url === b.cam.preview?.url,
);

function HlsVideo({ src, onFail, onReady }: { src: string; onFail: () => void; onReady: () => void }) {
	const ref = useRef<HTMLVideoElement>(null);
	// callbacks em ref: o efeito depende só do `src` e não recria o player quando o pai re-renderiza
	const cb = useRef({ onFail, onReady });
	cb.current = { onFail, onReady };

	useEffect(() => {
		const video = ref.current!;
		let alive = true;
		let hls: { destroy(): void } | null = null;
		const giveUp = () => {
			if (alive) cb.current.onFail();
		};
		const play = () => video.play().catch(() => {});
		const onPlaying = () => {
			if (alive) cb.current.onReady();
		};
		const onVisible = () => {
			if (document.visibilityState === "visible" && video.paused) play();
		};
		video.addEventListener("playing", onPlaying);
		document.addEventListener("visibilitychange", onVisible);

		if (video.canPlayType("application/vnd.apple.mpegurl")) {
			video.src = src; // Safari/iOS tocam HLS nativamente
			video.addEventListener("error", giveUp);
			play();
		} else {
			import("hls.js")
				.then(({ default: Hls }) => {
					if (!alive) return;
					if (!Hls.isSupported()) return giveUp();
					let tries = 0;
					const h = new Hls({ maxBufferLength: 8, liveSyncDurationCount: 3 });
					hls = h;
					h.on(Hls.Events.MANIFEST_PARSED, () => {
						tries = 0;
						play();
					});
					h.on(Hls.Events.ERROR, (_e, d) => {
						if (!d.fatal) return;
						if (++tries > 6) return giveUp();
						if (d.type === Hls.ErrorTypes.NETWORK_ERROR) setTimeout(() => alive && h.startLoad(), 1500 * tries);
						else if (d.type === Hls.ErrorTypes.MEDIA_ERROR) h.recoverMediaError();
						else giveUp();
					});
					h.loadSource(src);
					h.attachMedia(video);
				})
				.catch(giveUp);
		}
		return () => {
			alive = false;
			video.removeEventListener("playing", onPlaying);
			video.removeEventListener("error", giveUp);
			document.removeEventListener("visibilitychange", onVisible);
			hls?.destroy();
			video.removeAttribute("src");
			video.load();
		};
	}, [src]);
	return <video ref={ref} muted autoPlay playsInline />;
}
