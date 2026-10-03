import type { StateGeom } from "../../assets/br-states";

export interface BBox {
	mnLon: number;
	mxLon: number;
	mnLat: number;
	mxLat: number;
	spanLon: number;
	spanLat: number;
}

export function bbox(states: StateGeom[]): BBox {
	let mnLon = Infinity,
		mxLon = -Infinity,
		mnLat = Infinity,
		mxLat = -Infinity;
	for (const st of states)
		for (const r of st.rings)
			for (const [lon, lat] of r) {
				if (lon < mnLon) mnLon = lon;
				if (lon > mxLon) mxLon = lon;
				if (lat < mnLat) mnLat = lat;
				if (lat > mxLat) mxLat = lat;
			}
	return { mnLon, mxLon, mnLat, mxLat, spanLon: mxLon - mnLon, spanLat: mxLat - mnLat };
}

/** Equiretangular simples: graus → pixels, com escala uniforme e centralização. */
export function projector(b: BBox, w: number, h: number, pad = 16) {
	const s = Math.min((w - pad * 2) / b.spanLon, (h - pad * 2) / b.spanLat);
	const ox = (w - b.spanLon * s) / 2;
	const oy = (h - b.spanLat * s) / 2;
	const fwd = (lon: number, lat: number): [number, number] => [ox + (lon - b.mnLon) * s, oy + (b.mxLat - lat) * s];
	const inv = (x: number, y: number): [number, number] => [b.mnLon + (x - ox) / s, b.mxLat - (y - oy) / s];
	return { s, fwd, inv };
}
