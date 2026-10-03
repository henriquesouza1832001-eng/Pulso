import { useCallback, useEffect, useMemo, useState } from "react";
import type { PulsoEvent } from "@pulso/shared";
import { fold } from "./lib/text";
import { api } from "./lib/api";
import { useClock } from "./hooks/useClock";
import { usePolling } from "./hooks/usePolling";
import { Section } from "./components/layout/Section";
import { Footer } from "./components/layout/Footer";
import { usePolling } from "./hooks/usePolling";
import { Section } from "./components/layout/Section";
import { Footer } from "./components/layout/Footer";
import { PulseIndicator } from "./components/pulse/PulseIndicator";
import type { ForecastCardData } from "./components/sections/Forecasts";
import { MonitoredCities } from "./components/sections/MonitoredCities";
import { BrazilMap } from "./components/map/BrazilMap";
import { UfPanel } from "./components/sections/UfPanel";
import { OsintFeed } from "./components/feed/OsintFeed";
import { Sidebar } from "./components/layout/Sidebar";
import { DashTopBar } from "./components/layout/DashTopBar";
import { PulseCard } from "./components/cards/PulseCard";
import { TrendCard } from "./components/cards/TrendCard";
import { CitiesCard } from "./components/cards/CitiesCard";
import { HighlightsCard } from "./components/cards/HighlightsCard";
import { CategoryCard } from "./components/cards/CategoryCard";
import { SensorsCard } from "./components/cards/SensorsCard";
import { ForecastCard } from "./components/cards/ForecastCard";
import { RecentCard } from "./components/cards/RecentCard";
import { Briefings } from "./components/feed/Briefings";
import { BrazilMap } from "./components/map/BrazilMap";
import { UfPanel } from "./components/sections/UfPanel";
import { OsintFeed } from "./components/feed/OsintFeed";
import { Markets } from "./components/feed/Markets";
import { EventDetail } from "./components/events/EventDetail";
import { Briefings } from "./components/sections/Briefings";
import { Cameras } from "./components/sections/Cameras";
import { HistorySection } from "./components/sections/HistorySection";
import { Faq } from "./components/sections/Faq";
import { DashTopBar, Sidebar, type Filters } from "./components/dashboard/Shell";
import {
	CategoryCard,
	CitiesCard,
	ForecastCard,
	HighlightsCard,
	PulseCard,
	RecentCard,
	SensorsCard,
	TrendCard,
} from "./components/dashboard/Cards";
import { REGIONS } from "./components/dashboard/regions";
import { DEMO_CAMERAS, DEMO_EVENTS, DEMO_FORECASTS, DEMO_HISTORY } from "./data/demo";

const DEMO = import.meta.env.VITE_DEMO === "1";
const PREVIEW: string | undefined = import.meta.env.VITE_PREVIEW_BRANCH || undefined;

/**
 * PULSO — watch page vertical no molde do pizzint:
 * topo → identidade → indicador nacional → cidades → mapa → feed → módulos → arquivo.
 */
export function App() {
	const clock = useClock();
	const pulse = usePolling(api.pulseBR, 15_000);
	const eventsPoll = usePolling(api.events100, 15_000);
	const stats = usePolling(api.stats, 30_000);
	const history = usePolling(api.pulseHistoryBR, 60_000);
	const forecasts = usePolling(api.forecasts, 60_000);
	const track = usePolling(api.trackRecord, 300_000);
	const health = usePolling(api.health, 30_000);
	const stats = usePolling(api.stats, 15_000);
	const forecasts = usePolling(api.forecasts, 15_000);
	const history = usePolling(api.history, 60_000);
	const pulseHistory = usePolling(api.pulseHistory, 60_000);
	const track = usePolling(api.trackRecord, 300_000);
	const camsPoll = usePolling(api.cameras, 600_000);
	const health = usePolling(api.health, 30_000);

	const [selectedId, setSelectedId] = useState<string | null>(null);
	const [ufPanel, setUfPanel] = useState<string | null>(null);
	// Filtros globais (barra superior + abas do mapa): valem para o painel inteiro e para o feed.
	const [filters, setFilters] = useState<Filters>({ query: "", uf: null, category: null });
	const [region, setRegion] = useState<string | null>(null);
	const setFeedUf = useCallback((uf: string | null) => setFilters((f) => ({ ...f, uf })), []);
	const [, forceTick] = useState(0);

	// re-render leve a cada 10s para os "há Xs" andarem
	useEffect(() => {
		const id = setInterval(() => forceTick((n) => n + 1), 10_000);
		return () => clearInterval(id);
	}, []);

	const allEvents: PulsoEvent[] = useMemo(() => {
		const real = eventsPoll.data?.events ?? [];
		return DEMO ? [...real, ...DEMO_EVENTS] : real;
	}, [eventsPoll.data]);

	// Busca, categoria e região: recorte comum. A UF fica à parte porque o feed tem seletor próprio dela.
	const feedEvents = useMemo(() => {
		const q = fold(filters.query.trim());
		const ufs = region ? REGIONS[region] : null;
		return allEvents.filter(
			(e) =>
				(!filters.category || e.category === filters.category) &&
				(!ufs || (e.state && ufs.includes(e.state))) &&
				(!q || fold(`${e.title} ${e.city ?? ""} ${e.state ?? ""}`).includes(q)),
		);
	}, [allEvents, filters.query, filters.category, region]);
	const events = useMemo(
		() =>
			filters.uf === null
				? feedEvents
				: feedEvents.filter((e) => (filters.uf === "BR" ? !e.state : e.state === filters.uf)),
		[feedEvents, filters.uf],
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

	// Dossiê completo: vem do botão do resumo, sem abrir autom. no feed/briefing.
	const [dossierId, setDossierId] = useState<string | null>(null);
	const dossier = useMemo(
		() => allEvents.find((e) => e.event_id === dossierId) ?? null,
		[allEvents, dossierId],
	);
	const onDossier = useCallback((id: string) => {
		setDossierId(id);
		requestAnimationFrame(() =>
			document.getElementById("dossie")?.scrollIntoView({ behavior: "smooth", block: "start" }),
		);
	}, []);

	// Item do feed é sanfona: clicar abre o resumo, clicar de novo fecha. Esc fecha o que estiver aberto.
	const onSelect = useCallback((id: string) => setSelectedId((cur) => (cur === id ? null : id)), []);

	// Item do feed é sanfona: clicar abre o resumo, clicar de novo fecha. Esc fecha o que estiver aberto.
	const onSelect = useCallback((id: string) => setSelectedId((cur) => (cur === id ? null : id)), []);
	useEffect(() => {
		const onKey = (ev: KeyboardEvent) => {
			if (ev.key === "Escape") setSelectedId(null);
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, []);
	const onStateSelect = useCallback((uf: string) => {
		setUfPanel(uf);
		setFeedUf(uf);
	}, [setFeedUf]);
	// Alerta clicado no mapa: o dossiê e o item ficam no feed, então leva a página até lá.
	const onMapSelect = useCallback((id: string) => {
		setSelectedId(id);
		document.getElementById("feed")?.scrollIntoView({ behavior: "smooth", block: "start" });
	}, []);
	const apiOnline = !pulse.error || !!pulse.data;
	// "AO VIVO" = API respondendo e último Pulso com menos de 15 min (3 ciclos de coleta).
	const lastPulse = stats.data?.last_pulse_at ? Date.parse(stats.data.last_pulse_at) : null;
	const live = apiOnline && (lastPulse === null || Date.now() - lastPulse < 15 * 60_000);
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
				<div className="dshell">
					<Sidebar />
					<div className="dmain">
						<DashTopBar
							clock={clock}
							live={live}
							filters={filters}
							onFilters={setFilters}
							sourcesOnline={stats.data?.sources_online ?? onlineSources}
							sourcesTotal={stats.data?.sources_total ?? health.data?.sources.length ?? 0}
						/>
						{DEMO && <p className="dbanner">DADOS DE DEMONSTRAÇÃO</p>}
						{PREVIEW && (
							<p className="dbanner">PRÉVIA DA BRANCH {PREVIEW.toUpperCase()} · ainda não está na produção</p>
						)}

						<div id="painel" className="dgrid">
							<div className="g-left">
								<PulseCard pulse={pulse.data} />
								<TrendCard points={history.data?.points ?? []} forecasts={forecasts.data?.forecasts ?? []} />
							</div>
							<section id="mapa" className="dcard g-map">
								<header className="dmap-tabs" role="tablist" aria-label="região do mapa">
									{["Brasil", ...Object.keys(REGIONS)].map((r) => (
										<button
											key={r}
											role="tab"
											aria-selected={(region ?? "Brasil") === r}
											className={(region ?? "Brasil") === r ? "on" : ""}
											onClick={() => setRegion(r === "Brasil" ? null : r)}
										>
											{r}
										</button>
									))}
								</header>
								<BrazilMap events={events} selectedId={selectedId} onSelect={onMapSelect} onStateSelect={onStateSelect} />
							</section>
							<div className="g-right">
								<CitiesCard events={events} onSelect={onMapSelect} />
								<HighlightsCard events={events} onSelect={onMapSelect} />
							</div>
							<div className="g-cat">
								<CategoryCard events={events} />
							</div>
							<div className="g-sens">
								<SensorsCard health={health.data} stats={stats.data} cameras={camsPoll.data?.cameras.length ?? 0} />
							</div>
							<div className="g-fc">
								<ForecastCard
									forecasts={forecasts.data?.forecasts ?? []}
									notice={forecasts.data?.notice ?? null}
									track={track.data}
								/>
							</div>
							<div className="g-recent">
								<RecentCard events={events} onSelect={onMapSelect} />
							</div>
						</div>
						{ufPanel && (
							<UfPanel
								uf={ufPanel}
								events={events}
								onClose={() => setUfPanel(null)}
								onSelect={onMapSelect}
							/>
						)}
					</div>
				</div>

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
			</main>
			<Footer />
						</div>
					</div>
					{ufPanel && (
						<UfPanel
							uf={ufPanel}
							events={allEvents}
							onSelect={(id) => {
								setSelectedId(id); // vindo do painel do estado: sempre abre (não alterna)
								document.getElementById("feed")?.scrollIntoView({ behavior: "smooth", block: "start" });
							}}
							onClose={() => {
								// fechar o painel do estado também tira o recorte dele (volta para todos os estados)
								if (filters.uf === ufPanel) setFeedUf(null);
								setUfPanel(null);
							}}
						/>
					)}

			<main>
				<Section
					id="feed"
					kicker="monitoramento"
					title="feed osint"
					desc="relatos brutos das fontes públicas, agregados em eventos pelo motor · atualiza a cada 15 segundos · clique em um relato para ver o resumo e as fontes"
				>
					<div className="feedcols">
						<OsintFeed
							events={feedEvents}
							onSelect={onSelect}
							selectedId={selectedId}
							demo={DEMO}
							sourcesCount={health.data?.sources.length ?? 0}
							onlineSources={onlineSources}
							uf={filters.uf}
							onUfChange={setFeedUf}
							onDossier={onDossier}
						/>
							<OsintFeed
								events={events}
								filters={filters}
								onSelect={onSelect}
								onUfChange={setFeedUf}
								onDossier={onDossier}
							/>
							<div id="mercados" className="feedside">
								{DEMO && <Markets items={DEMO_FORECASTS} />}
								<div id="briefings" className="side-block">
									<div className="mkt-head">
										<span className="mkt-title">BRIEFINGS</span>
										<span className="dim">ANÁLISE · EVENTOS MAIS QUENTES</span>
									</div>
									<Briefings events={events} onDossier={onDossier} pageSize={5} minLevel={2} />
								</div>
								<div id="mercados-raw">
									<Markets
										items={marketItems}
										loading={!DEMO && forecasts.loading}
										error={DEMO ? null : forecasts.error}
									/>
								</div>
							</div>
							{dossier && (
								<div id="dossie" className="dossier-panel">
									<NewsDossier event={dossier} onClose={() => setDossierId(null)} />
								</div>
							)}
					</div>

					{dossier && (
						<div className="evdetail-wrap" id="dossie">
							<div className="evdetail-head">
								<span className="kicker">DOSSIÊ</span>
								<span className="dim">{dossier.event_id.toUpperCase()}</span>
								<button
									className="evshare"
									onClick={() =>
										void navigator.clipboard?.writeText(`${window.location.origin}${window.location.pathname}#feed`)
									}
								>
									COPIAR LINK ⧉
								</button>
								<button className="evclose" onClick={() => setDossierId(null)} aria-label="fechar dossiê">
									FECHAR ✕
								</button>
							</div>
							<EventDetail event={dossier} />
						</div>
					)}
				</Section>

				<Section
					id="cameras"
					kicker="ao vivo"
					title="câmeras"
					desc="só vias e praças · nunca pessoas · a prévia vem do player do próprio provedor"
				>
					<Cameras
						cameras={DEMO ? DEMO_CAMERAS : []}
						feeds={camsPoll.data?.cameras ?? []}
						focusUf={filters.uf}
						query={filters.query}
						pageSize={8}
					/>
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
				</div>
			</div>
		</>
	);
}
