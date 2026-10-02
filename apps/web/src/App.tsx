import { api } from "./api";
import { usePolling } from "./usePolling";
import { PulseGauge } from "./components/PulseGauge";
import { EventCard } from "./components/EventCard";

export function App() {
	const pulse = usePolling(api.pulseBR, 15_000);
	const events = usePolling(api.events, 15_000);

	return (
		<main className="wrap">
			<header className="top">
				<h1>PULSO</h1>
				<span className="mono dim">BRASIL · AO VIVO</span>
			</header>

			{pulse.data ? (
				<PulseGauge snapshot={pulse.data} updatedAt={pulse.updatedAt} />
			) : (
				<p className="dim">{pulse.error ? "API indisponível. Tentando novamente…" : "Carregando…"}</p>
			)}

			<section aria-label="Eventos">
				<h2 className="mono dim">TOP EVENTOS</h2>
				{events.data?.events.length === 0 && (
					<p className="panel dim">Nenhum evento detectado ainda. Aguardando o Engine.</p>
				)}
				<ul className="grid">
					{events.data?.events.map((e) => (
						<li key={e.event_id}>
							<EventCard event={e} />
						</li>
					))}
				</ul>
			</section>
		</main>
	);
}
