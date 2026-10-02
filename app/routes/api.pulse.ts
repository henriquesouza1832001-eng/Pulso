import { getPulse } from "~/lib/pulse.server";
import type { Route } from "./+types/api.pulse";

export async function loader({ context }: Route.LoaderArgs) {
	const data = await getPulse(context.cloudflare.env.DB);
	return Response.json(data, {
		headers: { "Cache-Control": "public, max-age=10, stale-while-revalidate=30" },
	});
}
