import { useEffect, useRef, useState } from "react";
import type { CameraFeed } from "@pulso/shared";

export interface CameraDef {
	id: string;
	label: string;
	city: string;
	state: string;
	status: "CRÍTICO" | "ELEVADO" | "ATENÇÃO" | "NORMAL";
}

/**
 * Câmeras ao vivo: "still" gerado localmente em canvas (ruído + faixas +
 * timestamp), aparência de CCTV. Nenhuma imagem externa, nenhum dado real.
 */
export function Cameras({ cameras, feeds = [] }: { cameras: CameraDef[]; feeds?: CameraFeed[] }) {
	if (cameras.length === 0 && feeds.length === 0)
		return <p className="state">NENHUMA CÂMERA AUTORIZADA NO ACERVO · AGUARDANDO PARCERIAS</p>;
	return (
		<>
			{cameras.length > 0 && (
				<div className="camgrid">
					{cameras.map((c) => (
						<CameraTile key={c.id} cam={c} />
					))}
				</div>
			)}
			{feeds.length > 0 && (
				<div className="camgrid">
					{feeds.map((f) => (
						<CameraFeedTile key={f.id} cam={f} />
					))}
				</div>
			)}
		</>
	);
}

/**
 * Câmera REAL de um provedor. O PULSO é só o placeholder: a prévia vem do player do próprio provedor (iframe ou HLS,
 * nunca retransmitida por nós) e o clique leva à página de origem. A prévia só carrega enquanto o cartão está visível
 * na tela (cortesia com o provedor e leve para o navegador); se falhar, sobra o cartão com o link.
 */
function CameraFeedTile({ cam }: { cam: CameraFeed }) {
	const box = useRef<HTMLDivElement>(null);
	const [visible, setVisible] = useState(false);
	const [failed, setFailed] = useState(false);

	useEffect(() => {
		const el = box.current;
		if (!el || typeof IntersectionObserver === "undefined") return setVisible(true);
		const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { rootMargin: "120px" });
		io.observe(el);
		return () => io.disconnect();
	}, []);

	const live = cam.preview !== null && !failed;
	return (
		<div className="camtile">
			<div className="camview" ref={box}>
				{live && visible && cam.preview!.type === "iframe" && (
					<iframe
						src={cam.preview!.url}
						title={cam.label}
						loading="lazy"
						referrerPolicy="no-referrer"
						sandbox="allow-scripts allow-same-origin"
						tabIndex={-1}
					/>
				)}
				{live && visible && cam.preview!.type === "hls" && (
					<HlsVideo src={cam.preview!.url} onFail={() => setFailed(true)} />
				)}
				{!(live && visible) && (
					<div className="camph">
						<span>{cam.provider.toUpperCase()}</span>
						<span className="dim">{live ? "carregando prévia…" : "ver ao vivo no site de origem"}</span>
					</div>
				)}
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
}

function HlsVideo({ src, onFail }: { src: string; onFail: () => void }) {
	const ref = useRef<HTMLVideoElement>(null);
	useEffect(() => {
		const video = ref.current!;
		let stop = () => {};
		let alive = true;
		if (video.canPlayType("application/vnd.apple.mpegurl")) {
			video.src = src; // Safari/iOS tocam HLS nativamente
			video.onerror = onFail;
		} else {
			import("hls.js")
				.then(({ default: Hls }) => {
					if (!alive) return;
					if (!Hls.isSupported()) return onFail();
					const hls = new Hls({ lowLatencyMode: true, maxBufferLength: 8 });
					hls.on(Hls.Events.ERROR, (_e, d) => d.fatal && onFail());
					hls.loadSource(src);
					hls.attachMedia(video);
					stop = () => hls.destroy();
				})
				.catch(onFail);
		}
		video.play().catch(() => {});
		return () => {
			alive = false;
			stop();
			video.removeAttribute("src");
			video.load();
		};
	}, [src, onFail]);
	return <video ref={ref} muted autoPlay playsInline />;
}

const STATUS_COLOR: Record<CameraDef["status"], string> = {
	CRÍTICO: "var(--red)",
	ELEVADO: "var(--org)",
	ATENÇÃO: "var(--amb)",
	NORMAL: "var(--grn)",
};

function CameraTile({ cam }: { cam: CameraDef }) {
	const ref = useRef<HTMLCanvasElement>(null);

	useEffect(() => {
		const canvas = ref.current!;
		const w = 320;
		const h = 180;
		const dpr = window.devicePixelRatio || 1;
		canvas.width = w * dpr;
		canvas.height = h * dpr;
		const g = canvas.getContext("2d")!;
		g.setTransform(dpr, 0, 0, dpr, 0, 0);

		// seed determinística por id
		let seed = [...cam.id].reduce((a, ch) => a + ch.charCodeAt(0), 0);
		const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);

		// céu noturno + horizonte
		g.fillStyle = "#0a0f16";
		g.fillRect(0, 0, w, h);
		g.fillStyle = "#0e141d";
		g.fillRect(0, h * 0.62, w, h * 0.38);
		// estrada em perspectiva
		g.fillStyle = "#121a24";
		g.beginPath();
		g.moveTo(w * 0.42, h);
		g.lineTo(w * 0.58, h);
		g.lineTo(w * 0.52, h * 0.62);
		g.lineTo(w * 0.48, h * 0.62);
		g.closePath();
		g.fill();
		// faixa central
		g.strokeStyle = "rgba(255,179,64,0.5)";
		g.setLineDash([6, 8]);
		g.beginPath();
		g.moveTo(w * 0.5, h);
		g.lineTo(w * 0.5, h * 0.64);
		g.stroke();
		g.setLineDash([]);
		// postes de luz
		for (let i = 0; i < 4; i++) {
			const x = w * (0.08 + i * 0.27);
			const ph = 40 + rnd() * 26;
			g.strokeStyle = "#233041";
			g.beginPath();
			g.moveTo(x, h * 0.62);
			g.lineTo(x, h * 0.62 - ph);
			g.stroke();
			g.fillStyle = "rgba(255,220,150,0.65)";
			g.fillRect(x - 2, h * 0.62 - ph - 2, 5, 3);
			g.fillStyle = "rgba(255,220,150,0.05)";
			g.beginPath();
			g.arc(x, h * 0.62 - ph, 18, 0, Math.PI * 2);
			g.fill();
		}
		// veículos como luzes
		for (let i = 0; i < 6; i++) {
			const y = h * 0.64 + rnd() * (h * 0.3);
			const x = w * 0.5 + (rnd() - 0.5) * w * 0.4;
			const s = 1 + (y - h * 0.64) / (h * 0.3) * 2;
			g.fillStyle = rnd() > 0.5 ? "rgba(255,90,70,0.9)" : "rgba(240,240,255,0.9)";
			g.fillRect(x, y, 2.5 * s, 1.5 * s);
		}
		// ruído de sensor
		for (let i = 0; i < 420; i++) {
			g.fillStyle = `rgba(160,190,220,${rnd() * 0.08})`;
			g.fillRect(rnd() * w, rnd() * h, 1, 1);
		}
		// vinheta
		const vg = g.createRadialGradient(w / 2, h / 2, h * 0.3, w / 2, h / 2, h);
		vg.addColorStop(0, "rgba(0,0,0,0)");
		vg.addColorStop(1, "rgba(0,0,0,0.5)");
		g.fillStyle = vg;
		g.fillRect(0, 0, w, h);
		// HUD do CCTV
		g.strokeStyle = "rgba(122,162,255,0.35)";
		g.strokeRect(8.5, 8.5, w - 17, h - 17);
		g.font = '10px "JetBrains Mono", monospace';
		g.fillStyle = "rgba(122,162,255,0.8)";
		g.fillText(cam.id, 14, 22);
		g.fillText(new Date().toLocaleDateString("pt-BR"), 14, h - 14);
		g.textAlign = "right";
		g.fillText(
			new Date().toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo", hour12: false }),
			w - 14,
			h - 14,
		);
	}, [cam.id]);

	return (
		<div className="camtile">
			<canvas ref={ref} style={{ width: "100%", display: "block" }} />
			<div className="caminfo">
				<span className="nm">{cam.label.toUpperCase()}</span>
				<span className="loc dim">
					{cam.city.toUpperCase()} · {cam.state}
				</span>
				<span className="st" style={{ color: STATUS_COLOR[cam.status] }}>
					● {cam.status}
				</span>
			</div>
		</div>
	);
}
