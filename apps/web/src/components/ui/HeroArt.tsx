import { useEffect, useRef } from "react";
import { BR_STATES } from "../../assets/br-states";
import { bbox } from "../map/projection";

/** Marca d'água: Brasil em matriz de pontos atrás do hero, quase invisível. */
export function HeroArt() {
	const ref = useRef<HTMLCanvasElement>(null);

	useEffect(() => {
		const canvas = ref.current!;
		const bb = bbox(BR_STATES);
		const draw = () => {
			const w = 520;
			const h = Math.round(w * (bb.spanLat / bb.spanLon));
			const dpr = window.devicePixelRatio || 1;
			canvas.width = w * dpr;
			canvas.height = h * dpr;
			const g = canvas.getContext("2d")!;
			g.setTransform(dpr, 0, 0, dpr, 0, 0);
			g.clearRect(0, 0, w, h);
			const s = Math.min(w / bb.spanLon, h / bb.spanLat);
			const ox = (w - bb.spanLon * s) / 2;
			const oy = (h - bb.spanLat * s) / 2;

			const inPoly = (x: number, y: number, poly: [number, number][]) => {
				let c = false;
				for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
					const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
					if (((yi > y) !== (yj > y)) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
				}
				return c;
			};

			const step = 7;
			for (let px = 0; px < w; px += step)
				for (let py = 0; py < h; py += step) {
					const lon = bb.mnLon + (px - ox) / s;
					const lat = bb.mxLat - (py - oy) / s;
					let inside = false;
					for (const st of BR_STATES) {
						for (const r of st.rings)
							if (r.length > 5 && inPoly(lon, lat, r)) {
								inside = true;
								break;
							}
						if (inside) break;
					}
					if (inside) {
						g.fillStyle = "rgba(154,160,166,0.10)";
						g.fillRect(px, py, 2, 2);
					}
				}
		};
		draw();
	}, []);

	return <canvas ref={ref} className="heroart" aria-hidden style={{ width: 520, height: "auto" }} />;
}
