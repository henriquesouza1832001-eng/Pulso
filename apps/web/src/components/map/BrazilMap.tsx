import { useEffect, useMemo, useRef, useState } from "react";
import type { PulsoEvent } from "@pulso/shared";
import { BR_STATES } from "../../assets/br-states";
import { bbox, projector } from "./projection";

const LVC = ["", "#3ddc84", "#ffb340", "#ff8a3d", "#ff4545", "#ff1744"];
const LAND = "#131a22";
const BORDER = "#3a4653";
const BORDER_HI = "#55636f";
const ACC = "#3ba4ff";
const BSB: [number, number] = [-47.93, -15.78];
const ZOOMS = [1, 1.45, 2];

const UF_NAME: Record<string, string> = {
	AC: "ACRE", AL: "ALAGOAS", AP: "AMAPÁ", AM: "AMAZONAS", BA: "BAHIA", CE: "CEARÁ",
	DF: "DISTRITO FEDERAL", ES: "ESPÍRITO SANTO", GO: "GOIÁS", MA: "MARANHÃO", MT: "MATO GROSSO",
	MS: "MATO GROSSO DO SUL", MG: "MINAS GERAIS", PA: "PARÁ", PB: "PARAÍBA", PR: "PARANÁ",
	PE: "PERNAMBUCO", PI: "PIAUÍ", RJ: "RIO DE JANEIRO", RN: "RIO GRANDE DO NORTE",
	RS: "RIO GRANDE DO SUL", RO: "RONDÔNIA", RR: "RORAIMA", SC: "SANTA CATARINA",
	SP: "SÃO PAULO", SE: "SERGIPE", TO: "TOCANTINS",
};

interface Layers {
	estados: boolean;
	cidades: boolean;
	alertas: boolean;
	conexoes: boolean;
	heatmap: boolean;
	grade: boolean;
}

const LAYER_ITEMS: Array<[keyof Layers, string]> = [
	["estados", "Estados"],
	["cidades", "Cidades monitoradas"],
	["alertas", "Alertas ativos"],
	["conexoes", "Conexões"],
	["heatmap", "Heatmap de intensidade"],
	["grade", "Grade de coordenadas"],
];

/** Textura de terreno determinística (padrão de ruído reutilizado). */
function makeTerrainPattern(g: CanvasRenderingContext2D): CanvasPattern | null {
	const c = document.createElement("canvas");
	c.width = 90;
	c.height = 90;
	const cg = c.getContext("2d")!;
	let s = 1234567;
	const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
	for (let y = 0; y < 90; y += 3)
		for (let x = 0; x < 90; x += 3) {
			const v = rnd();
			if (v > 0.82) {
				cg.fillStyle = `rgba(120,140,160,${0.05 + rnd() * 0.06})`;
				cg.fillRect(x, y, 2, 2);
			} else if (v < 0.1) {
				cg.fillStyle = `rgba(0,0,0,${0.12 + rnd() * 0.1})`;
				cg.fillRect(x, y, 2, 2);
			}
		}
	return g.createPattern(c, "repeat");
}

/**
 * Mapa do Brasil em camadas — módulo de intelligence com geometria real:
 * terreno texturizado, heatmap com halo por evento, arcos visíveis a partir
 * do núcleo DF, grade de coordenadas, zoom por botões/roda e arraste (pan).
 */
export function BrazilMap({
	events,
	selectedId,
	onSelect,
	onStateSelect,
}: {
	events: PulsoEvent[];
	selectedId: string | null;
	onSelect: (id: string) => void;
	onStateSelect: (uf: string) => void;
}) {
	const wrapRef = useRef<HTMLDivElement>(null);
	const canvasRef = useRef<HTMLCanvasElement>(null);
	const [hover, setHover] = useState<string | null>(null);
	const [layers, setLayers] = useState<Layers>({
		estados: true,
		cidades: true,
		alertas: true,
		conexoes: true,
		heatmap: true,
		grade: true,
	});
	const [zi, setZi] = useState(0);
	const [pan, setPan] = useState<[number, number]>([0, 0]);
	const [tip, setTip] = useState<{ x: number; y: number; title: string; lines?: string[] } | null>(null);
	const [coords, setCoords] = useState("[ mova o cursor sobre o mapa ]");
	const dragRef = useRef<{ x: number; y: number; px: number; py: number; moved: boolean } | null>(null);

	const bb = useMemo(() => bbox(BR_STATES), []);

	const perState = useMemo(() => {
		const m = new Map<string, { count: number; level: number; pulse: number; worst: PulsoEvent }>();
		for (const e of events) {
			if (!e.state) continue;
			const cur = m.get(e.state);
			if (!cur) m.set(e.state, { count: 1, level: e.alert_level, pulse: e.pulse, worst: e });
			else {
				cur.count++;
				cur.level = Math.max(cur.level, e.alert_level);
				cur.pulse = Math.max(cur.pulse, e.pulse);
				if (e.pulse > cur.worst.pulse) cur.worst = e;
			}
		}
		return m;
	}, [events]);

	const geoEvents = useMemo(
		() => events.filter((e) => e.latitude != null && e.longitude != null),
		[events],
	);

	const cityDots = useMemo(() => {
		const m = new Map<string, { lon: number; lat: number }>();
		for (const e of geoEvents) {
			const k = `${e.city ?? ""}|${e.state ?? ""}`;
			if (!m.has(k)) m.set(k, { lon: e.longitude!, lat: e.latitude! });
		}
		return [...m.values()];
	}, [geoEvents]);

	useEffect(() => {
		const wrap = wrapRef.current!;
		const canvas = canvasRef.current!;
		let raf = 0;
		let stopped = false;
		let last = 0;

		const draw = (ts: number) => {
			if (stopped) return;
			const w = wrap.clientWidth;
			const h = Math.round(w * (bb.spanLat / bb.spanLon));
			const dpr = window.devicePixelRatio || 1;
			if (canvas.width !== Math.round(w * dpr)) {
				canvas.width = Math.round(w * dpr);
				canvas.height = Math.round(h * dpr);
				canvas.style.height = `${h}px`;
			}
			const g = canvas.getContext("2d")!;
			g.setTransform(dpr, 0, 0, dpr, 0, 0);
			g.clearRect(0, 0, w, h);

			const z = ZOOMS[zi];
		const cx = w / 2, cy = h / 2;
		const { s: pscale, fwd, inv } = projector(bb, w, h, 26);
		const S = (p: [number, number]): [number, number] => [
			cx + (p[0] - cx) * z + pan[0],
			cy + (p[1] - cy) * z + pan[1],
		];
		type Inv = (x: number, y: number) => [number, number];
		const invZoom = (x: number, y: number): [number, number] =>
			inv(cx + (x - pan[0] - cx) / z, cy + (y - pan[1] - cy) / z);
		(canvas as HTMLCanvasElement & { __inv?: Inv }).__inv = invZoom;

		const traceState = (rings: number[][][]) => {
			g.beginPath();
			for (const r of rings) {
				if (r.length < 6) continue;
				r.forEach(([lon, lat], i) => {
					const [x, y] = S(fwd(lon, lat));
					if (i === 0) g.moveTo(x, y);
					else g.lineTo(x, y);
				});
				g.closePath();
			}
		};

		const stateAt = (lon: number, lat: number): string | null => {
			for (const st of BR_STATES)
				for (const r of st.rings) {
					if (r.length < 6) continue;
					let inside = false;
					for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
						const xi = r[i][0], yi = r[i][1], xj = r[j][0], yj = r[j][1];
						if (((yi > lat) !== (yj > lat)) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi)
							inside = !inside;
					}
					if (inside) return st.uf;
				}
			return null;
		};
		(canvas as HTMLCanvasElement & { __stateAt?: (lon: number, lat: number) => string | null }).__stateAt = stateAt;

		// fundo oceânico + halo externo do país (sombra cartográfica)
		g.fillStyle = "#070a0e";
		g.fillRect(0, 0, w, h);
		g.save();
		g.shadowColor = "rgba(59,164,255,0.18)";
		g.shadowBlur = 26;
		for (const st of BR_STATES) {
			traceState(st.rings);
			g.fillStyle = LAND;
			g.fill();
		}
		g.restore();

		// textura de terreno sobre a terra
		const terrain = makeTerrainPattern(g);
		if (terrain) {
			for (const st of BR_STATES) {
				traceState(st.rings);
				g.fillStyle = terrain;
				g.fill();
			}
		}

		// grade de coordenadas
		if (layers.grade) {
			g.strokeStyle = "rgba(122,162,255,0.08)";
			g.lineWidth = 1;
			g.font = '8px "JetBrains Mono", monospace';
			g.fillStyle = "rgba(122,162,255,0.35)";
			for (let lat = -30; lat <= 5; lat += 5) {
				const [, y] = S(fwd(bb.mnLon, lat));
				if (y < -10 || y > h + 10) continue;
				g.beginPath();
				g.moveTo(0, Math.round(y) + 0.5);
				g.lineTo(w, Math.round(y) + 0.5);
				g.stroke();
				g.fillText(`${Math.abs(lat)}°S`, 4, y - 3);
			}
			for (let lon = -70; lon <= -35; lon += 5) {
				const [x] = S(fwd(lon, 0));
				if (x < -10 || x > w + 10) continue;
				g.beginPath();
				g.moveTo(Math.round(x) + 0.5, 0);
				g.lineTo(Math.round(x) + 0.5, h);
				g.stroke();
				g.fillText(`${Math.abs(lon)}°W`, x + 3, 10);
			}
		}

		// heatmap: tint estadual + halo radial por evento
		if (layers.heatmap) {
			for (const st of BR_STATES) {
				const info = perState.get(st.uf);
				if (!info || info.level < 2) continue;
				traceState(st.rings);
				g.globalAlpha = info.level >= 4 ? 0.20 : info.level === 3 ? 0.14 : 0.09;
				g.fillStyle = LVC[info.level];
				g.fill();
				g.globalAlpha = 1;
			}
			for (const e of geoEvents) {
				const [x, y] = S(fwd(e.longitude!, e.latitude!));
				const rad = 16 + (e.pulse / 100) * 30;
				const gr = g.createRadialGradient(x, y, 2, x, y, rad);
				const c = LVC[e.alert_level];
				gr.addColorStop(0, c + "38"); // hex alpha
				gr.addColorStop(1, c + "00");
				g.fillStyle = gr;
				g.beginPath();
				g.arc(x, y, rad, 0, Math.PI * 2);
				g.fill();
			}
		}

		// conexões: arcos visíveis partindo do núcleo DF
		if (layers.conexoes) {
			const hub = S(fwd(BSB[0], BSB[1]));
			for (const e of geoEvents) {
				const p = S(fwd(e.longitude!, e.latitude!));
				const mx = (hub[0] + p[0]) / 2;
				const my = (hub[1] + p[1]) / 2 - Math.hypot(p[0] - hub[0], p[1] - hub[1]) * 0.22;
				g.strokeStyle = "rgba(59,164,255,0.34)";
				g.lineWidth = 1;
				g.beginPath();
				g.moveTo(hub[0], hub[1]);
				g.quadraticCurveTo(mx, my, p[0], p[1]);
				g.stroke();
				// nó de destino
				g.fillStyle = "rgba(59,164,255,0.5)";
				g.fillRect(p[0] - 1, p[1] - 1, 2, 2);
			}
			g.fillStyle = ACC;
			g.beginPath();
			g.arc(hub[0], hub[1], 3, 0, Math.PI * 2);
			g.fill();
			g.strokeStyle = "rgba(59,164,255,0.4)";
			g.beginPath();
			g.arc(hub[0], hub[1], 6.5, 0, Math.PI * 2);
			g.stroke();
			g.font = '700 8.5px "JetBrains Mono", monospace';
			g.fillStyle = ACC;
			g.fillText("NÚCLEO DF", hub[0] + 9, hub[1] + 3);
		}

		// divisas estaduais (+hover) e contorno do estado do evento selecionado
		const selUF = geoEvents.find((e) => e.event_id === selectedId)?.state ?? null;
		g.lineJoin = "round";
		for (const st of BR_STATES) {
			const isHover = hover === `uf:${st.uf}`;
			const isSel = st.uf === selUF;
			traceState(st.rings);
			g.strokeStyle = isSel ? ACC : isHover ? ACC : BORDER;
			g.lineWidth = isSel ? 2 : isHover ? 1.6 : 1;
			g.stroke();
			if (isHover || isSel) {
				g.fillStyle = "rgba(59,164,255,0.07)";
				g.fill();
			}
		}

		// contorno nacional forte por cima
		g.strokeStyle = BORDER_HI;
		g.lineWidth = 1.2;
		for (const st of BR_STATES) {
			traceState(st.rings);
			g.stroke();
		}

		// siglas
		if (layers.estados) {
			g.textAlign = "center";
			for (const st of BR_STATES) {
				const r = st.rings[0];
				if (!r || r.length < 6) continue;
				let sx = 0, sy = 0, mnx = Infinity, mxx = -Infinity;
				for (const [lon, lat] of r) {
					sx += lon;
					sy += lat;
					if (lon < mnx) mnx = lon;
					if (lon > mxx) mxx = lon;
				}
				const [x, y] = S(fwd(sx / r.length, sy / r.length));
				const info = perState.get(st.uf);
				g.fillStyle = info && info.count > 0 ? "rgba(237,237,237,0.85)" : "#5b6771";
				// sigla acompanha o zoom (raiz quadrada para não explodir)
				const size = ((mxx - mnx) * pscale < 0.055 ? 8 : 9.5) * Math.sqrt(z);
				g.font = `700 ${size.toFixed(1)}px "JetBrains Mono", monospace`;
				const busy = geoEvents.some((e) => {
					const [ex, ey] = S(fwd(e.longitude!, e.latitude!));
					return Math.hypot(ex - x, ey - y) < 14;
				});
				if (!busy) g.fillText(st.uf, x, y + 3);
			}
			g.textAlign = "left";
		}

		// cidades monitoradas: pontos brancos com anel
		if (layers.cidades) {
			for (const c of cityDots) {
				const [x, y] = S(fwd(c.lon, c.lat));
				g.fillStyle = "rgba(237,237,237,0.9)";
				g.beginPath();
				g.arc(x, y, 2.2, 0, Math.PI * 2);
				g.fill();
				g.strokeStyle = "rgba(10,10,10,0.9)";
				g.lineWidth = 1;
				g.beginPath();
				g.arc(x, y, 3.2, 0, Math.PI * 2);
				g.stroke();
			}
		}

		// alertas: marcador de nível + anel duplo + pulso respirando
		if (layers.alertas) {
			geoEvents.forEach((e, i) => {
				const [x, y] = S(fwd(e.longitude!, e.latitude!));
				const c = LVC[e.alert_level];
				const r = 3 + (e.pulse / 100) * 3.5;
				// halo pulsante (fase própria por evento)
				const ph = ((ts / 1400 + i * 0.37) % 1 + 1) % 1;
				g.strokeStyle = c;
				g.globalAlpha = (1 - ph) * 0.55;
				g.lineWidth = 1.4;
				g.beginPath();
				g.arc(x, y, r + 3 + ph * 9, 0, Math.PI * 2);
				g.stroke();
				g.globalAlpha = 1;
				g.fillStyle = c;
				g.beginPath();
				g.arc(x, y, r, 0, Math.PI * 2);
				g.fill();
				g.strokeStyle = c;
				g.globalAlpha = 0.5;
				g.lineWidth = 1;
				g.beginPath();
				g.arc(x, y, r + 4, 0, Math.PI * 2);
				g.stroke();
				g.globalAlpha = 1;
				const on = e.event_id === selectedId || hover === `ev:${e.event_id}`;
				if (on) {
					g.font = '700 9.5px "JetBrains Mono", monospace';
					g.fillStyle = "#ededed";
					g.fillText(`${e.state ?? ""} · ${e.title.slice(0, 30).toUpperCase()}`, x + 12, y - 7);
					const b = 9 + r;
					g.strokeStyle = "#ededed";
					g.lineWidth = 1;
					g.beginPath();
					for (const [dx, dy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]] as const) {
						g.moveTo(x + dx * b, y + dy * b - dy * 4);
						g.lineTo(x + dx * b, y + dy * b);
						g.lineTo(x + dx * b - dx * 4, y + dy * b);
					}
					g.stroke();
				}
			});
		}

		// barra de escala (km) — canto inferior esquerdo
		{
			const kmPerPx = (111.32 * Math.cos((-14 * Math.PI) / 180)) / (pscale * z);
			let km = z >= 2 ? 200 : 500;
			let barW = km / kmPerPx;
			while (barW > 130) {
				km /= 2;
				barW = km / kmPerPx;
			}
			const bx = 14;
			const by = h - 16;
			g.strokeStyle = "rgba(237,237,237,0.75)";
			g.lineWidth = 1;
			g.beginPath();
			g.moveTo(bx, by - 4);
			g.lineTo(bx, by);
			g.lineTo(bx + barW, by);
			g.lineTo(bx + barW, by - 4);
			g.stroke();
			g.font = '8px "JetBrains Mono", monospace';
			g.fillStyle = "rgba(237,237,237,0.7)";
			g.fillText(`${km} KM`, bx + barW + 6, by - 1);
		}
		};

		// anima enquanto a aba está visível (pulso dos alertas); ~35fps é suficiente
		const loop = (ts: number) => {
			if (stopped) return;
			if (ts - last > 28) {
				last = ts;
				draw(ts);
			}
			raf = requestAnimationFrame(loop);
		};
		raf = requestAnimationFrame(loop);
		const onVis = () => {
			cancelAnimationFrame(raf);
			if (!document.hidden) raf = requestAnimationFrame(loop);
		};
		document.addEventListener("visibilitychange", onVis);
		return () => {
			stopped = true;
			cancelAnimationFrame(raf);
			document.removeEventListener("visibilitychange", onVis);
		};
	}, [bb, layers, zi, pan, perState, geoEvents, cityDots, selectedId, hover]);

	// ---- interação ----
	const locate = (ev: React.MouseEvent<HTMLCanvasElement>) => {
		const canvas = canvasRef.current!;
		const rect = canvas.getBoundingClientRect();
		const x = ev.clientX - rect.left;
		const y = ev.clientY - rect.top;
		const inv = (canvas as HTMLCanvasElement & { __inv?: (x: number, y: number) => [number, number] }).__inv;
		return { x, y, lonLat: inv ? inv(x, y) : null };
	};

	const onWheel = (ev: React.WheelEvent<HTMLCanvasElement>) => {
		ev.preventDefault();
		setZi((i) => Math.max(0, Math.min(ZOOMS.length - 1, i + (ev.deltaY < 0 ? 1 : -1))));
	};

	const onDown = (ev: React.MouseEvent<HTMLCanvasElement>) => {
		dragRef.current = { x: ev.clientX, y: ev.clientY, px: pan[0], py: pan[1], moved: false };
	};

	const onMove = (ev: React.MouseEvent<HTMLCanvasElement>) => {
		// arraste (pan)
		if (dragRef.current && (ev.buttons & 1)) {
			const d = dragRef.current;
			if (Math.hypot(ev.clientX - d.x, ev.clientY - d.y) > 4) d.moved = true;
			setPan([d.px + (ev.clientX - d.x), d.py + (ev.clientY - d.y)]);
			setTip(null);
			return;
		}
		const { x, y, lonLat } = locate(ev);
		if (!lonLat) return;
		const [lon, lat] = lonLat;
		setCoords(`${Math.abs(lat).toFixed(2)}°S ${Math.abs(lon).toFixed(2)}°W · ZOOM ${ZOOMS[zi]}×`);

		for (const e of geoEvents) {
			const dx = (e.longitude! - lon) * 0.55;
			const dy = e.latitude! - lat;
			if (Math.hypot(dx, dy) < 0.9) {
				setHover(`ev:${e.event_id}`);
				setTip({
					x,
					y,
					title: e.title,
					lines: [
						`N${e.alert_level} · PULSO ${e.pulse} · ${e.signal_count} SINAIS · ${e.source_count} FONTES`,
						`${[e.city, e.state].filter(Boolean).join("/") ?? ""} · CONF ${e.confidence}%`,
					],
				});
				return;
			}
		}
		for (const st of BR_STATES) {
			for (const r of st.rings) {
				if (r.length < 6) continue;
				let inside = false;
				for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
					const xi = r[i][0], yi = r[i][1], xj = r[j][0], yj = r[j][1];
					if (((yi > lat) !== (yj > lat)) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi)
						inside = !inside;
				}
				if (inside) {
					setHover(`uf:${st.uf}`);
					const info = perState.get(st.uf);
					const evsIn = events
						.filter((e) => e.state === st.uf)
						.sort((a, b) => b.pulse - a.pulse)
						.slice(0, 3)
						.map((e) => `N${e.alert_level} ${e.title.slice(0, 34).toUpperCase()}`);
					setTip({
						x,
						y,
						title: info
							? `${UF_NAME[st.uf] ?? st.uf} · ${info.count} EVENTO(S) · PULSO ${info.pulse}`
							: `${UF_NAME[st.uf] ?? st.uf} · SEM EVENTOS ATIVOS`,
						lines: evsIn.length ? evsIn : undefined,
					});
					return;
				}
			}
		}
		setHover(null);
		setTip(null);
	};

	const onUp = () => {
		dragRef.current = null;
	};

	const onClick = (ev: React.MouseEvent<HTMLCanvasElement>) => {
		// se arrastou, não seleciona
		if (dragRef.current?.moved) return;
		const { lonLat } = locate(ev);
		if (!lonLat) return;
		const [lon, lat] = lonLat;
		for (const e of geoEvents) {
			const dx = (e.longitude! - lon) * 0.55;
			const dy = e.latitude! - lat;
			if (Math.hypot(dx, dy) < 0.9) {
				onSelect(e.event_id);
				return;
			}
		}
		for (const st of BR_STATES) {
			for (const r of st.rings) {
				if (r.length < 6) continue;
				let inside = false;
				for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
					const xi = r[i][0], yi = r[i][1], xj = r[j][0], yj = r[j][1];
					if (((yi > lat) !== (yj > lat)) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi)
						inside = !inside;
				}
				if (inside) {
					onStateSelect(st.uf);
					return;
				}
			}
		}
	};

	const reset = () => {
		setZi(0);
		setPan([0, 0]);
	};

	return (
		<div className="mapwrap" ref={wrapRef}>
			<canvas
				id="map-canvas"
				ref={canvasRef}
				onMouseMove={onMove}
				onMouseLeave={() => {
					onUp();
					setHover(null);
					setTip(null);
				}}
				onMouseDown={onDown}
				onMouseUp={onUp}
				onWheel={onWheel}
				onClick={onClick}
				role="img"
				aria-label="Mapa do Brasil em camadas com atividade por estado"
			/>

			<div className="map-layers">
				<span className="ml-title">CAMADAS</span>
				{LAYER_ITEMS.map(([key, label]) => (
					<label key={key} className="ml-item">
						<input
							type="checkbox"
							checked={layers[key]}
							onChange={(e) => setLayers((l) => ({ ...l, [key]: e.target.checked }))}
						/>
						{label.toUpperCase()}
					</label>
				))}
			</div>

			<div className="map-zoom">
				<button onClick={() => setZi((i) => Math.min(i + 1, ZOOMS.length - 1))} aria-label="aproximar">+</button>
				<button onClick={() => setZi((i) => Math.max(i - 1, 0))} aria-label="afastar">−</button>
				<button onClick={reset} aria-label="redefinir vista">⤢</button>
			</div>

			{tip && (
				<div className="map-tip" style={{ left: tip.x + 14, top: tip.y + 16 }}>
					<span className="mt-title">{tip.title.toUpperCase()}</span>
					{tip.lines?.map((l, i) => (
						<span key={i} className="mt-line">
							{l}
						</span>
					))}
				</div>
			)}

			<div className="map-legend" aria-hidden>
				{[
					[1, "N1 NORMAL"],
					[2, "N2 ATENÇÃO"],
					[3, "N3 ELEVADO"],
					[4, "N4 CRÍTICO"],
					[5, "N5 EMERGÊNCIA"],
				].map(([lv, label]) => (
					<span key={lv as number} className="lg-row">
						<i className="sw" style={{ background: LVC[lv as number] }} />
						{label}
					</span>
				))}
				<span className="lg-row">
					<i className="sw sw-city" />
					CIDADE
				</span>
				<span className="lg-row">
					<i className="sw sw-arc" />
					CONEXÃO
				</span>
			</div>

			<span className="mapcoords">{coords}</span>
		</div>
	);
}
