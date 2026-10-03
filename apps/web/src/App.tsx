import { useCallback, useEffect, useMemo, useState } from "react";
import type { PulsoEvent } from "@pulso/shared";
import { api } from "./lib/api";
import { useClock } from "./hooks/useClock";
import { usePolling } from "./hooks/usePolling";
import { TopBar } from "./components/layout/TopBar";
import { Hero } from "./components/layout/Hero";
import { Section } from "./components/layout/Section";
import { Footer } from "./components/layout/Footer";
import { PulseIndicator } from "./components/pulse/PulseIndicator";
import type { ForecastCardData } from "./components/sections/Forecasts";
import { MonitoredCities } from "./components/sections/MonitoredCities";
import { BrazilMap } from "./components/map/BrazilMap";
import { StateList } from "./components/sections/StateList";
import { UfPanel } from "./components/sections/UfPanel";
import { OsintFeed } from "./components/feed/OsintFeed";
import { Markets } from "./components/feed/Markets";
import { SourceMonitor } from "./components/system/SourceMonitor";
import { EventDetail } from "./components/events/EventDetail";
import { Briefings } from "./components/sections/Briefings";
import { Cameras } from "./components/sections/Cameras";
import { HistorySection } from "./components/sections/HistorySection";
import { Faq } from "./components/sections/Faq";
import { DEMO_CAMERAS, DEMO_EVENTS, DEMO_FORECASTS, DEMO_HISTORY } from "./data/demo";

const DEMO = import.meta.env.VITE_DEMO === "1";

/**
 * PULSO — watch page vertical no molde do pizzint:
 * topo → identidade → indicador nacional → cidades → mapa → feed → módulos → arquivo.
 */
export function App() {
	const clock = useClock();
	const pulse = usePolling(api.pulseBR, 15_000);
	const eventsPoll = usePolling(api.events, 15_000);
	const health = usePolling(api.health, 30_000);
	const stats = usePolling(api.stats, 15_000);
	const forecasts = usePolling(api.forecasts, 15_000);
	const history = usePolling(api.history, 60_000);
	const pulseHistory = usePolling(api.pulseHistory, 60_000);

	const [selectedId, setSelectedId] = useState<string | null>(null);
	const [ufPanel, setUfPanel] = useState<string | null>(null);
	// Estado em foco no feed: escolher uma UF no mapa/lista também recorta o feed para ela.
	const [feedUf, setFeedUf] = useState<string | null>(null);
	const [, forceTick] = useState(0);

	// re-render leve a cada 10s para os "há Xs" andarem
	useEffect(() => {
		const id = setInterval(() => forceTick((n) => n + 1), 10_000);
		return () => clearInterval(id);
	}, []);

	const events: PulsoEvent[] = useMemo(() => {
		const real = eventsPoll.data?.events ?? [];
		return DEMO ? [...real, ...DEMO_EVENTS] : real;
	}, [eventsPoll.data]);

	const selected = useMemo(
		() => events.find((e) => e.event_id === selectedId) ?? null,
		[events, selectedId],
	);

	const marketItems: ForecastCardData[] = useMemo(() => {
		if (DEMO) {
			return DEMO_FORECASTS.map((f, i) => ({
				id: `demo-forecast-${i}`,
				question: f.q,
				probability: f.yes / 100,
				intervalLow: null,
				intervalHigh: null,
				horizonMinutes: f.horizonMinutes ?? null,
				scope: "DEMO",
				method: "demo",
				evidence: {},
				resolvesAt: null,
				experimental: true,
				demo: true,
				drivers: f.drivers,
			}));
		}
		return (forecasts.data?.forecasts ?? []).map((f) => ({
			id: f.forecast_id,
			question: f.question,
			probability: f.probability,
			intervalLow: f.interval_low,
			intervalHigh: f.interval_high,
			horizonMinutes: f.horizon_minutes,
			scope: f.scope,
			method: `${f.method} v${f.method_version}`,
			evidence: f.evidence,
			resolvesAt: f.resolves_at,
			experimental: f.experimental ?? true,
		}));
	}, [forecasts.data]);
	const historyEntries = DEMO ? DEMO_HISTORY : (history.data?.entries ?? []);

	const onSelect = useCallback((id: string) => setSelectedId(id), []);
	const onStateSelect = useCallback((uf: string) => {
		setUfPanel(uf);
		setFeedUf(uf);
	}, []);
	// Alerta clicado no mapa: o dossiê e o item ficam no feed, então leva a página até lá.
	const onMapSelect = useCallback((id: string) => {
		setSelectedId(id);
		document.getElementById("feed")?.scrollIntoView({ behavior: "smooth", block: "start" });
	}, []);
	const apiOnline = !pulse.error || !!pulse.data;
	const onlineSources = health.data?.sources.filter((s) => s.status === "ONLINE").length ?? 0;

	return (
		<>
			<TopBar
				clock={clock}
				apiOnline={apiOnline}
				demo={DEMO}
				sourcesCount={stats.data?.sources_total ?? health.data?.sources.length ?? 0}
				alertsCount={stats.data?.alerts ?? null}
				score={pulse.data?.score ?? null}
				level={pulse.data?.alert_level ?? 3}
			/>

			<Hero />

			<PulseIndicator
				pulse={pulse}
				sourcesOnline={stats.data?.sources_online ?? null}
				eventsCount={stats.data?.active_events ?? null}
				signals2h={stats.data?.signals_2h ?? null}
				statesActive={stats.data?.states_active ?? null}
				pulseHistory={pulseHistory.data?.points ?? []}
				pulseHistoryLoading={pulseHistory.loading}
				pulseHistoryError={pulseHistory.error}
			/>

			<main>
				<Section
					id="cidades"
					kicker="geografia"
					title="cidades sob observação"
					desc="as localidades com maior atividade agora — status, intensidade e atividade nas últimas 24h"
					cta="ver todas no mapa"
					ctaHref="#mapa"
				>
					<MonitoredCities events={events} onSelect={onSelect} />
				</Section>

				<Section
					id="mapa"
					kicker="geografia"
					title="mapa do brasil"
					desc="geometria real por unidade da federação · camadas funcionais · clique num estado ou num alerta para abrir o dossiê"
					cta="abrir o feed por região"
					ctaHref="#feed"
				>
					<div className="mapcols">
						<BrazilMap
							events={events}
							selectedId={selectedId}
							onSelect={onMapSelect}
							onStateSelect={onStateSelect}
						/>
						<div className="mapside">
							<span className="sidehead">PULSO POR UF · CLIQUE PARA ABRIR</span>
							<StateList events={events} onStateSelect={onStateSelect} />
							<div className="sidesrc">
								<span className="sidehead">FONTES ATIVAS</span>
								<SourceMonitor health={health.data} />
							</div>
						</div>
					</div>
					{ufPanel && (
						<UfPanel
							uf={ufPanel}
							events={events}
							onSelect={(id) => {
								onSelect(id);
								document.getElementById("feed")?.scrollIntoView({ behavior: "smooth", block: "start" });
							}}
							onClose={() => setUfPanel(null)}
						/>
					)}
				</Section>

				<Section
					id="feed"
					kicker="monitoramento"
					title="feed osint"
					desc="relatos brutos das fontes públicas, agregados em eventos pelo motor · atualiza a cada 15 segundos"
				>
					<div className="feedcols">
						<OsintFeed
							events={events}
							onSelect={onSelect}
							selectedId={selectedId}
							demo={DEMO}
							sourcesCount={health.data?.sources.length ?? 0}
							onlineSources={onlineSources}
							uf={feedUf}
							onUfChange={setFeedUf}
						/>
						<div id="mercados">
							<Markets
								items={marketItems}
								loading={!DEMO && forecasts.loading}
								error={DEMO ? null : forecasts.error}
							/>
						</div>
					</div>

					{selected && (
						<div className="evdetail-wrap">
							<div className="evdetail-head">
								<span className="kicker">DOSSIÊ</span>
								<span className="dim">{selected.event_id.toUpperCase()}</span>
								<button
									className="evshare"
									onClick={() =>
										void navigator.clipboard?.writeText(`${window.location.origin}${window.location.pathname}#feed`)
									}
								>
									COPIAR LINK ⧉
								</button>
								<button className="evclose" onClick={() => setSelectedId(null)} aria-label="fechar dossiê">
									FECHAR ✕
								</button>
							</div>
							<EventDetail event={selected} />
						</div>
					)}
				</Section>

				<Section
					id="briefings"
					kicker="análise"
					title="briefings"
					desc="leitura curta dos eventos mais quentes — sempre ligada às fontes e ao dossiê"
					cta="ver todos os eventos"
					ctaHref="#feed"
				>
					<Briefings events={events} onSelect={onSelect} />
				</Section>

				<Section
					id="cameras"
					kicker="sensores"
					title="câmeras autorizadas"
					desc="somente sensores ambientais públicos de vias e praças — nunca vigilância de pessoas"
				>
					<Cameras cameras={DEMO ? DEMO_CAMERAS : []} />
				</Section>

				<Section
					id="historico"
					kicker="arquivo"
					title="histórico de inteligência"
					desc="momentos de nível alto registrados pelo motor"
				>
					<HistorySection
						entries={historyEntries}
						loading={!DEMO && history.loading}
						error={DEMO ? null : history.error}
					/>
				</Section>

				<Section
					id="faq"
					kicker="referência"
					title="o que é o pulso?"
					desc="perguntas diretas, respostas curtas"
					last
				>
					<Faq />
				</Section>
			</main>

			<Footer
				clock={clock}
				apiOnline={apiOnline}
				sourcesCount={stats.data?.sources_total ?? health.data?.sources.length ?? 0}
				demo={DEMO}
			/>
		</>
	);
}
