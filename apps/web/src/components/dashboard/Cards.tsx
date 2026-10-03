import { useMemo, useState } from "react";
import type { Forecast, PulsoEvent, PulseSnapshot } from "@pulso/shared";
import type { HealthSnapshot, PulsePoint, StatsSnapshot, TrackRecord } from "../../lib/api";
import { ago, CATEGORY_PT, LEVEL_PT } from "../../lib/format";
import { CAT_ICON, catColor, Icon } from "../ui/Icon";
import { SourceMonitor } from "../system/SourceMonitor";

/* Cartões do painel. Regra: só dado real da API; o que ainda não existe aparece como vazio honesto. */

const LVC = ["", "var(--lv1)", "var(--lv2)", "var(--lv3)", "var(--lv4)", "var(--lv5)"];
const place = (e: PulsoEvent) =>
	[e.city, e.state].filter(Boolean).join(" - ") || (e.category === "INTERNATIONAL" ? "internacional" : "nacional");
const pct = (p: number) => `${Math.round(p * 100)}%`;

export function Card({
	id,
	title,
	sub,
	action,
	className,
	children,
}: {
	id?: string;
	title: string;
	sub?: string;
	action?: React.ReactNode;
	className?: string;
	children: React.ReactNode;
}) {
	return (
		<section id={id} className={`dcard${className ? ` ${className}` : ""}`}>
			<header className="dcard-h">
				<h2>
					{title} {sub && <small>{sub}</small>}
				</h2>
				{action}
			</header>
			{children}
		</section>
	);
}

/** PULSO BRASIL: número, variação real em 2 h e escala 1–5. */
export function PulseCard({ pulse }: { pulse: PulseSnapshot | null }) {
	const lv = pulse?.alert_level ?? 0;
	const d = pulse?.delta_2h;
	return (
		<Card title="PULSO BRASIL" className="dpulse">
			<div className="dpulse-main">
				<span className="dpulse-n" style={{ color: LVC[lv] || "var(--tx2)" }}>
					{pulse ? pulse.score : "--"}
				</span>
				<span className="dpulse-d">
					{d == null ? (
						<small className="dim">sem ponto de 2 h atrás</small>
					) : (
						<>
							<b className={d > 0 ? "l4" : d < 0 ? "grn" : "dim"}>
								{d > 0 ? "▲ +" : d < 0 ? "▼ " : "= "}
								{d}
							</b>
							<small className="dim">nas últimas 2 horas</small>
						</>
					)}
				</span>
			</div>
			{pulse && (
				<span className="dpulse-badge" style={{ background: LVC[lv] }}>
					NÍVEL {lv} · {(LEVEL_PT as Record<number, string>)[lv] ?? pulse.label}
				</span>
			)}
			<div className="dpulse-scale" aria-label="escala de níveis">
				{[1, 2, 3, 4, 5].map((n) => (
					<span key={n} className={n === lv ? "on" : ""} style={{ borderColor: LVC[n], color: LVC[n] }}>
						<b>{n}</b>
						<small>{(LEVEL_PT as Record<number, string>)[n]}</small>
					</span>
				))}
			</div>
		</Card>
	);
}

/** Tendência nacional: série real das últimas 6 h + previsão NOWCAST registrada (com faixa e selo). */
export function TrendCard({ points, forecasts }: { points: PulsePoint[]; forecasts: Forecast[] }) {
	const w = 320, h = 110, pad = 18;
	const t0 = points.length ? Date.parse(points[0].timestamp) : 0;
	const t1 = points.length ? Date.parse(points[points.length - 1].timestamp) : 1;
	const x = (t: string) => pad + ((Date.parse(t) - t0) / Math.max(1, t1 - t0)) * (w - pad - 4);
	const y = (v: number) => h - 14 - (v / 100) * (h - 24);
	const d = points.map((p, i) => `${i ? "L" : "M"}${x(p.timestamp).toFixed(1)} ${y(p.score).toFixed(1)}`).join(" ");
	const nowcast = forecasts
		.filter((f) => f.status === "open" && f.scope === "BR" && f.metric === "pulse")
		.sort((a, b) => a.horizon_minutes - b.horizon_minutes)[0];
	return (
		<Card title="TENDÊNCIA NACIONAL" sub="(ÚLTIMAS 6 HORAS)" className="dtrend">
			{points.length < 2 ? (
				<p className="state">COLETANDO HISTÓRICO…</p>
			) : (
				<svg viewBox={`0 0 ${w} ${h}`} className="dtrend-svg" role="img" aria-label="Pulso Brasil nas últimas 6 horas">
					{[0, 50, 100].map((v) => (
						<g key={v}>
							<line x1={pad} x2={w} y1={y(v)} y2={y(v)} stroke="var(--ln0)" />
							<text x={0} y={y(v) + 3} fill="var(--tx2)" fontSize="8">
								{v}
							</text>
						</g>
					))}
					<path d={`${d} L${x(points[points.length - 1].timestamp)} ${y(0)} L${pad} ${y(0)} Z`} fill="rgba(255,138,61,0.12)" />
					<path d={d} fill="none" stroke="var(--org)" strokeWidth="1.8" />
					<text x={pad} y={h - 2} fill="var(--tx2)" fontSize="8">
						-6h
					</text>
					<text x={w - 26} y={h - 2} fill="var(--tx2)" fontSize="8">
						agora
					</text>
				</svg>
			)}
			{nowcast ? (
				<div className="dtrend-fc">
					<b style={{ color: "var(--org)" }}>{pct(nowcast.probability)}</b>
					<span>
						chance de o Pulso BR ficar {nowcast.comparator === "gte" ? "≥" : "≤"} {nowcast.threshold} em{" "}
						{nowcast.horizon_minutes} min
						<small className="dim">
							{" "}
							· faixa {pct(nowcast.interval_low)}–{pct(nowcast.interval_high)}
						</small>
					</span>
					{nowcast.experimental !== false && <em className="dtag">EXPERIMENTAL</em>}
				</div>
			) : (
				<p className="dim dsmall">nenhuma previsão nacional aberta agora</p>
			)}
		</Card>
	);
}

/** Cidades em alerta: agregadas dos eventos ativos (maior Pulso e nível por cidade). */
export function CitiesCard({ events, onSelect }: { events: PulsoEvent[]; onSelect: (id: string) => void }) {
	const rows = useMemo(() => {
		const m = new Map<string, { label: string; pulse: number; level: number; n: number; top: PulsoEvent }>();
		for (const e of events) {
			if (!e.city || !e.state) continue;
			const k = `${e.city}|${e.state}`;
			const r = m.get(k);
			if (!r) m.set(k, { label: `${e.city} - ${e.state}`, pulse: e.pulse, level: e.alert_level, n: 1, top: e });
			else {
				r.n++;
				if (e.pulse > r.pulse) Object.assign(r, { pulse: e.pulse, top: e });
				r.level = Math.max(r.level, e.alert_level);
			}
		}
		return [...m.values()].sort((a, b) => b.level - a.level || b.pulse - a.pulse).slice(0, 6);
	}, [events]);
	return (
		<Card title="CIDADES EM ALERTA" sub="(AGORA)" action={<a className="dlink" href="#feed">Ver todas</a>}>
			{rows.length === 0 ? (
				<p className="state">NENHUMA CIDADE COM EVENTO ATIVO</p>
			) : (
				<table className="dtable">
					<thead>
						<tr>
							<th>Cidade</th>
							<th>Pulso</th>
							<th>Nível</th>
							<th>Eventos</th>
						</tr>
					</thead>
					<tbody>
						{rows.map((r) => (
							<tr key={r.label} onClick={() => onSelect(r.top.event_id)} title={r.top.title}>
								<td>
									<Icon name={CAT_ICON[r.top.category] ?? "activity"} size={13} color={catColor(r.top.category)} /> {r.label}
								</td>
								<td>
									<span className="dpill" style={{ background: LVC[r.level] }}>
										{r.pulse}
									</span>
								</td>
								<td style={{ color: LVC[r.level] }}>N{r.level}</td>
								<td className="dim">{r.n}</td>
							</tr>
						))}
					</tbody>
				</table>
			)}
		</Card>
	);
}

/** Eventos em destaque: maior nível primeiro, depois Pulso. */
export function HighlightsCard({ events, onSelect }: { events: PulsoEvent[]; onSelect: (id: string) => void }) {
	const top = useMemo(
		() => [...events].sort((a, b) => b.alert_level - a.alert_level || b.pulse - a.pulse).slice(0, 4),
		[events],
	);
	return (
		<Card title="EVENTOS EM DESTAQUE" sub="(TEMPO REAL)" action={<a className="dlink" href="#feed">Ver todos</a>}>
			{top.length === 0 && <p className="state">AGUARDANDO EVENTOS</p>}
			{top.map((e) => (
				<article key={e.event_id} className="dhl" onClick={() => onSelect(e.event_id)}>
					<span className="dhl-lv" style={{ background: LVC[e.alert_level] }}>
						PULSO {e.pulse}
						<small>N{e.alert_level}</small>
					</span>
					<div>
						<p className="dhl-t">
							<Icon name={CAT_ICON[e.category] ?? "activity"} size={13} color={catColor(e.category)} /> {e.title}
						</p>
						<p className="dhl-m dim">
							{place(e)} · {ago(e.updated_at)}
						</p>
						<p className="dhl-chips">
							<span>{CATEGORY_PT[e.category]}</span>
							<span>
								{e.source_count} fonte{e.source_count === 1 ? "" : "s"}
							</span>
							<span>{e.signal_count} sinais</span>
							<span>conf {e.confidence}%</span>
						</p>
					</div>
				</article>
			))}
		</Card>
	);
}

/** Atividade por categoria: sinais dos eventos atualizados nas últimas 2 h (e 24 h, para comparar). */
export function CategoryCard({ events }: { events: PulsoEvent[] }) {
	const rows = useMemo(() => {
		const now = Date.now();
		const m = new Map<string, { h2: number; h24: number }>();
		for (const e of events) {
			const r = m.get(e.category) ?? { h2: 0, h24: 0 };
			r.h24 += e.signal_count;
			if (now - Date.parse(e.updated_at) <= 2 * 3600_000) r.h2 += e.signal_count;
			m.set(e.category, r);
		}
		return [...m.entries()].filter(([c]) => c !== "OTHER").sort((a, b) => b[1].h2 - a[1].h2 || b[1].h24 - a[1].h24).slice(0, 6);
	}, [events]);
	const max = Math.max(1, ...rows.map(([, r]) => r.h2));
	return (
		<Card title="ATIVIDADE POR CATEGORIA" sub="(SINAIS · 2H / 24H)">
			{rows.map(([c, r]) => (
				<div key={c} className="dcat">
					<span className="dcat-n">
						<Icon name={CAT_ICON[c] ?? "activity"} size={13} color={catColor(c)} />{" "}
						{(CATEGORY_PT as Record<string, string>)[c].charAt(0) + (CATEGORY_PT as Record<string, string>)[c].slice(1).toLowerCase()}
					</span>
					<span className="dcat-bar">
						<i style={{ width: `${(r.h2 / max) * 100}%`, background: catColor(c) }} />
					</span>
					<b>{r.h2}</b>
					<small className="dim">/{r.h24}</small>
				</div>
			))}
			{rows.length === 0 && <p className="state">SEM ATIVIDADE</p>}
		</Card>
	);
}

/** Sensores ativos: anel online/total + câmeras + painel de fontes (dropdown). */
export function SensorsCard({
	health,
	stats,
	cameras,
}: {
	health: HealthSnapshot | null;
	stats: StatsSnapshot | null;
	cameras: number;
}) {
	const on = stats?.sources_online ?? health?.sources.filter((s) => s.status === "ONLINE").length ?? 0;
	const tot = stats?.sources_total ?? health?.sources.length ?? 0;
	const r = 34, c = 2 * Math.PI * r, frac = tot ? on / tot : 0;
	return (
		<Card id="sensores" title="SENSORES ATIVOS" className="dsens">
			<div className="dsens-top">
				<svg viewBox="0 0 84 84" className="dring" role="img" aria-label={`${on} de ${tot} fontes online`}>
					<circle cx="42" cy="42" r={r} stroke="var(--ln1)" strokeWidth="7" fill="none" />
					<circle
						cx="42"
						cy="42"
						r={r}
						stroke="var(--grn)"
						strokeWidth="7"
						fill="none"
						strokeDasharray={`${c * frac} ${c}`}
						transform="rotate(-90 42 42)"
					/>
					<text x="42" y="46" textAnchor="middle" fill="var(--tx0)" fontSize="13" fontWeight="800">
						{on}/{tot}
					</text>
				</svg>
				<ul className="dsens-l">
					<li>
						<span>Fontes online</span>
						<b className="grn">{on}</b>
					</li>
					<li>
						<span>Com problema</span>
						<b className={tot - on ? "l4" : ""}>{tot - on}</b>
					</li>
					<li>
						<span>Câmeras públicas</span>
						<b>{cameras || "--"}</b>
					</li>
					<li>
						<span>Sinais (2h / 24h)</span>
						<b>
							{stats?.signals_2h ?? "--"} / {stats?.signals_24h ?? "--"}
						</b>
					</li>
				</ul>
			</div>
			<SourceMonitor health={health} />
		</Card>
	);
}

/** Previsões registradas (NOWCAST): probabilidade + faixa + selo; nunca como fato. */
export function ForecastCard({
	forecasts,
	notice,
	track,
}: {
	forecasts: Forecast[];
	notice: string | null;
	track: TrackRecord | null;
}) {
	const scopes = useMemo(
		() => [...new Set(forecasts.filter((f) => f.status === "open").map((f) => f.scope))].sort((a, b) => (a === "BR" ? -1 : b === "BR" ? 1 : a.localeCompare(b))),
		[forecasts],
	);
	const [scope, setScope] = useState<string | null>(null);
	const cur = scope ?? scopes[0] ?? null;
	const list = forecasts.filter((f) => f.status === "open" && f.scope === cur).sort((a, b) => b.probability - a.probability).slice(0, 3);
	const m = track?.methods?.[0];
	return (
		<Card id="previsao" title="PREVISÃO" sub="(NOWCAST)" className="dfc">
			{scopes.length > 0 && (
				<select value={cur ?? ""} onChange={(e) => setScope(e.target.value)} aria-label="escopo da previsão">
					{scopes.map((s) => (
						<option key={s} value={s}>
							{s === "BR" ? "Brasil" : s.replace("UF:", "")}
						</option>
					))}
				</select>
			)}
			{list.length === 0 ? (
				<p className="state">SEM PREVISÃO ABERTA · O MODELO PRECISA DE HISTÓRICO</p>
			) : (
				list.map((f) => (
					<div key={f.forecast_id} className="dfc-row">
						<p className="dfc-q">{f.question}</p>
						<div className="dfc-p">
							<b>{pct(f.probability)}</b>
							<span className="dfc-band" title={`faixa ${pct(f.interval_low)}–${pct(f.interval_high)}`}>
								<i
									style={{
										left: `${f.interval_low * 100}%`,
										width: `${Math.max(1, (f.interval_high - f.interval_low) * 100)}%`,
									}}
								/>
								<em style={{ left: `${f.probability * 100}%` }} />
							</span>
							<small className="dim">
								{pct(f.interval_low)}–{pct(f.interval_high)}
							</small>
							{f.experimental !== false && <em className="dtag">EXPERIMENTAL</em>}
						</div>
					</div>
				))
			)}
			<p className="dim dsmall">
				{notice ? notice.split(".")[0] + "." : "Previsão, não fato."}
				{m && m.mean_brier != null && (
					<>
						{" "}
						Acerto do método: Brier {m.mean_brier.toFixed(3)} em {m.n_resolved} previsões resolvidas.
					</>
				)}
			</p>
		</Card>
	);
}

/** Feeds recentes: os eventos atualizados por último. */
export function RecentCard({ events, onSelect }: { events: PulsoEvent[]; onSelect: (id: string) => void }) {
	const list = useMemo(
		() => [...events].sort((a, b) => +new Date(b.updated_at) - +new Date(a.updated_at)).slice(0, 6),
		[events],
	);
	return (
		<Card title="FEEDS RECENTES" action={<a className="dlink" href="#feed">Feed completo</a>}>
			<ul className="drecent">
				{list.map((e) => (
					<li key={e.event_id} onClick={() => onSelect(e.event_id)}>
						<Icon name={CAT_ICON[e.category] ?? "activity"} size={13} color={catColor(e.category)} />
						<span className="drecent-t">
							<b>{CATEGORY_PT[e.category]}</b> — {e.title}
						</span>
						<small className="dim">{ago(e.updated_at)}</small>
					</li>
				))}
			</ul>
		</Card>
	);
}
