import { useEffect } from "react";
import { useFetcher } from "react-router";
import { getPulse } from "~/lib/pulse.server";
import type { Route } from "./+types/home";

export const meta: Route.MetaFunction = () => [
	{ title: "Pulso — o que está acontecendo no Brasil agora" },
	{
		name: "description",
		content: "Radar de notícias em tempo real: intensidade, fontes e evolução.",
	},
];

export async function loader({ context }: Route.LoaderArgs) {
	return getPulse(context.cloudflare.env.DB);
}

export default function Home({ loaderData }: Route.ComponentProps) {
	const fetcher = useFetcher<typeof loaderData>();
	const data = fetcher.data ?? loaderData;

	// Atualização leve: revalida a cada 15 s sem refresh manual.
	useEffect(() => {
		const id = setInterval(() => fetcher.load("/api/pulse"), 15_000);
		return () => clearInterval(id);
	}, [fetcher]);

	const filled = Math.round(data.score / 5);
	return (
		<main className="mx-auto max-w-5xl px-4 py-8">
			<header className="flex items-center justify-between border-b border-line pb-4">
				<h1 className="font-mono text-2xl font-extrabold tracking-widest text-pulso">
					PULSO
				</h1>
				<span className="font-mono text-xs text-neutral-500">BRASIL · AO VIVO</span>
			</header>

			<section className="py-10" aria-label="Pulso nacional">
				<p className="font-mono text-xs tracking-widest text-neutral-500">
					PULSO NACIONAL
				</p>
				<p className="font-mono text-8xl font-extrabold tabular-nums">{data.score}</p>
				<p className="font-mono text-pulso" aria-hidden>
					{"█".repeat(filled)}
					<span className="text-line">{"░".repeat(20 - filled)}</span>
				</p>
				<p className="mt-2 text-sm font-semibold tracking-wider text-alerta">
					{data.label}
				</p>
				<p className="mt-1 text-xs text-neutral-500">
					Intensidade informacional, não aprovação nem veracidade.
				</p>
			</section>

			<section aria-label="Acontecendo agora">
				<h2 className="mb-3 font-mono text-xs tracking-widest text-neutral-500">
					ACONTECENDO AGORA
				</h2>
				{data.events.length === 0 ? (
					<p className="rounded border border-line bg-panel p-6 text-sm text-neutral-400">
						Nenhum evento detectado ainda. Aguardando a primeira coleta das fontes.
					</p>
				) : (
					<ul className="grid gap-3 sm:grid-cols-2">
						{data.events.map((e) => (
							<li key={e.id} className="rounded border border-line bg-panel p-4">
								<p className="font-mono text-lg font-extrabold text-pulso">
									{e.pulso_score}
								</p>
								<h3 className="font-semibold">{e.title}</h3>
								<p className="mt-1 text-xs text-neutral-500">
									{e.article_count} matérias · {e.source_count} fontes
								</p>
							</li>
						))}
					</ul>
				)}
			</section>
		</main>
	);
}
