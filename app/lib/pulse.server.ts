import { activityLabel } from "./score";

export interface TopEvent {
	id: string;
	title: string;
	pulso_score: number;
	article_count: number;
	source_count: number;
	updated_at: number;
}

export async function getPulse(db: D1Database) {
	const now = Math.floor(Date.now() / 1000);
	const { results } = await db
		.prepare(
			`SELECT id, title, pulso_score, article_count, source_count, updated_at
			 FROM events WHERE updated_at >= ?1
			 ORDER BY pulso_score DESC LIMIT 10`,
		)
		.bind(now - 24 * 3600)
		.all<TopEvent>();

	const scores = results.map((e) => e.pulso_score);
	// Média ponderada para o topo: os eventos mais intensos pesam mais no índice nacional.
	const national = scores.length
		? Math.round(
				scores.reduce((acc, s, i) => acc + s * (scores.length - i), 0) /
					scores.reduce((acc, _, i) => acc + (scores.length - i), 0),
			)
		: 0;

	return {
		score: national,
		label: activityLabel(national),
		events: results,
		updatedAt: now,
	};
}
