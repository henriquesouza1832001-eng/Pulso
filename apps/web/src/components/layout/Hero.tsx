/**
 * Hero editorial no molde do pizzint: título markdown ("# PULSO"),
 * tagline, linha de contexto e ações. Sem glow, sem fonte display.
 */
export function Hero() {
	return (
		<header className="hero">
			<h1>
				<span className="hash">#</span> PULSO
			</h1>
			<p className="tagline">O Brasil em tempo real</p>
			<p className="hero-sub">
				sinais públicos · eventos · intensidade — 27 unidades da federação sob observação contínua
			</p>
			<div className="hero-actions">
				<button
					className="hbtn"
					onClick={() => {
						const url = window.location.href;
						if (navigator.share) void navigator.share({ title: "PULSO — Brasil em tempo real", url });
						else void navigator.clipboard.writeText(url);
					}}
				>
					COMPARTILHAR ↗
				</button>
				<a className="hbtn ghost" href="#feed">
					ENTRAR NO FEED →
				</a>
			</div>
		</header>
	);
}
