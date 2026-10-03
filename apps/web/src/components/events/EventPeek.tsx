import { useEffect, useState } from "react";
import type { PulsoEvent } from "@pulso/shared";
import type { EventDetail as EventDetailData, SignalRow } from "../../lib/api";
import { api } from "../../lib/api";
import { ago } from "../../lib/format";
import { LevelTag } from "../ui/LevelTag";

const MAX_SOURCES = 5;
const CACHE_MS = 60_000;

/** Sinais por evento, guardados 1 min: abrir/fechar/reabrir a sanfona não refaz a chamada. */
const cache = new Map<string, { at: number; p: Promise<EventDetailData> }>();
function loadDetail(id: string): Promise<EventDetailData> {
	const hit = cache.get(id);
	if (hit && Date.now() - hit.at < CACHE_MS) return hit.p;
	const p = api.event(id);
	p.catch(() => cache.delete(id)); // erro não fica guardado
	cache.set(id, { at: Date.now(), p });
	return p;
}

/**
 * Resumo do evento aberto no próprio item (feed ou briefing): resumo, números e as fontes com link para a matéria
 * original. O dossiê completo (pontuação, todos os sinais) fica a um clique em "ver dossiê completo".
 */
export function EventPeek({
	event,
	onDossier,
	showSummary = true,
}: {
	event: PulsoEvent;
	onDossier: (id: string) => void;
	showSummary?: boolean;
}) {
	const [signals, setSignals] = useState<SignalRow[] | null>(null);
	const [err, setErr] = useState(false);
	const isDemo = event.event_id.startsWith("demo-");

	useEffect(() => {
		let alive = true;
		setSignals(null);
		setErr(false);
		if (isDemo) return;
		loadDetail(event.event_id)
			.then((d) => alive && setSignals(d.signals))
			.catch(() => alive && setErr(true));
		return () => {
			alive = false;
		};
	}, [event.event_id, isDemo]);

	const place = [event.city, event.state].filter(Boolean).join("/") || "localizando";
	return (
		// cliques aqui dentro (links, botão) não fecham a sanfona
		<div className="peek" onClick={(ev) => ev.stopPropagation()}>
			{showSummary && (
				<p className="peek-sum">
					{tidySummary(event.summary) ??
						`${event.signal_count} sinais convergindo de ${event.source_count} fonte(s) independente(s).`}
				</p>
			)}
			<div className="peek-meta">
				<LevelTag level={event.alert_level} compact />
				<span>conf {event.confidence}%</span>
				<span>sev {event.severity}</span>
				<span>{place}</span>
				<span>detectado {ago(event.detected_at)}</span>
			</div>
			<span className="peek-h">
				FONTES · {event.source_count} independente{event.source_count === 1 ? "" : "s"} · {event.signal_count} sina
				{event.signal_count === 1 ? "l" : "is"}
			</span>
			{err && <p className="peek-empty">fontes indisponíveis agora · veja o dossiê completo</p>}
			{!err && !signals && !isDemo && <p className="peek-empty">carregando fontes…</p>}
			{signals && signals.length > 0 && (
				<ul className="peek-src">
					{signals.slice(0, MAX_SOURCES).map((s) => (
						<li key={s.signal_id}>
							<span className="t">{brTime(s.timestamp)}</span>
							<span className="s">{s.source_name}</span>
							{s.url ? (
								<a className="x" href={s.url} target="_blank" rel="noopener noreferrer" title={s.title}>
									{s.title} ↗
								</a>
							) : (
								<span className="x" title={s.title}>
									{s.title}
								</span>
							)}
						</li>
					))}
				</ul>
			)}
			<div className="peek-foot">
				{signals && signals.length > MAX_SOURCES && (
					<span className="dim">+{signals.length - MAX_SOURCES} no dossiê</span>
				)}
				<button className="peek-more" onClick={() => onDossier(event.event_id)}>
					VER DOSSIÊ COMPLETO ↓
				</button>
			</div>
		</div>
	);
}

function brTime(iso: string): string {
	return new Date(iso).toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo", hour12: false, hour: "2-digit", minute: "2-digit" });
}

/** Teto de caracteres do resumo gravado pelo motor: texto com esse tamanho chegou cortado. */
const SUMMARY_CAP = 500;

/**
 * O resumo vem do texto das matérias cortado em SUMMARY_CAP caracteres e pode terminar no meio da palavra
 * ("A Guarda Costeira d"). Só nesse caso, fecha na última frase completa (ou no último espaço + "…"). Texto mais curto
 * está inteiro, mesmo sem ponto final ("morreu ao sofrer um infarto"), e fica como veio.
 */
export function tidySummary(text: string | null): string | null {
	const t = text?.replace(/\s+/g, " ").trim();
	if (!t) return null;
	if ((text ?? "").length < SUMMARY_CAP || /[.!?…»"”)]$/.test(t)) return t;
	const end = Math.max(t.lastIndexOf(". "), t.lastIndexOf("! "), t.lastIndexOf("? "));
	if (end >= 40) return t.slice(0, end + 1);
	const sp = t.lastIndexOf(" ");
	return `${sp > 0 ? t.slice(0, sp) : t}…`;
}
