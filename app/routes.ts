import { type RouteConfig, index, route } from "@react-router/dev/routes";

export default [
	index("routes/home.tsx"),
	route("api/pulse", "routes/api.pulse.ts"),
] satisfies RouteConfig;
