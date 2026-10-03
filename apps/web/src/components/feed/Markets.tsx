import type { Forecast } from "../sections/Forecasts";
import { Sparkline } from "../sections/Forecasts";

/**
 * Mercados — equivalentes das odds do pizzint: probabilidade estatística
 * de cenários derivados dos sinais públicos. SIM/NÃO com barra fina.
 */
export function Markets({ items }: { items: Forecast[] }) {
	if (items.length === 0)
		return (
			<div className="mkt">
				<div className="mkt-head">
					<span className="mkt-title">MERCADOS</span>
					<span className="dim">ODDS</span>
				</div>
				<p className="state">MODELO PREDITIVO OFFLINE · PULSO-ML AINDA NÃO TREINADO COM DADOS REAIS</p>
			</div>
		);
	return (
		<div className="mkt">
			<div className="mkt-head">
				<span className="mkt-title">MERCADOS</span>
				<span className="dim">ODDS AO VIVO</span>
			</div>
			<div className="mkt-list">
				{items.map((f) => (
					<article key={f.q} className="mkt-card">
						<p className="mkt-q">{f.q}</p>
						<div className="mkt-row">
							<span className="mkt-yes">SIM {f.yes}%</span>
							<span className="dim">NÃO {100 - f.yes}%</span>
						</div>
						<div className="mbar">
							<div className="y" style={{ width: `${f.yes}%` }} />
							<div className="n" style={{ width: `${100 - f.yes}%` }} />
						</div>
						<Sparkline seed={f.q.length * 7} trend={f.yes} />
						<p className="mkt-drivers dim">base: {f.drivers}</p>
					</article>
				))}
			</div>
			<p className="mkt-note dim">probabilidade estatística de sinais públicos, não certeza e não aposta.</p>
		</div>
	);
}
