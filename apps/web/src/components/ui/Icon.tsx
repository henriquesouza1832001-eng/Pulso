import type { CSSProperties } from "react";

/** Ícones de linha em SVG próprio. Sem emoji, sem dependência. */
const PATHS: Record<string, string> = {
	zap: "M13 2 3 14h7l-1 8 10-12h-7l1-8z",
	alert: "M12 3 22 20H2L12 3zm0 6v5m0 3v.5",
	activity: "M3 12h4l3-7 4 14 3-7h4",
	live: "M12 12h.01M8.5 8.5a5 5 0 0 0 0 7m7-7a5 5 0 0 1 0 7M5.6 5.6a9 9 0 0 0 0 12.8m12.8-12.8a9 9 0 0 1 0 12.8",
	arrow: "M5 12h14m-6-6 6 6-6 6",
	pin: "M12 21s-7-5.1-7-11a7 7 0 0 1 14 0c0 5.9-7 11-7 11zm0-8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
	cam: "M23 7l-7 5 7 5V7zM14 7H3a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V8a1 1 0 0 0-1-1z",
	flame: "M12 22c4 0 7-2.7 7-7 0-3-2-5.5-3.5-7C15 6 14 4 14 2c-2 1.5-3 4-3 6 0 0-1.5-1-2-3-2 2-4 4.5-4 10 0 4.3 3 7 7 7z",
	wind: "M3 8h9a3 3 0 1 0-3-3M3 12h13a3 3 0 1 1-3 3M3 16h6a2 2 0 1 1-2 2",
	shield: "M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z",
	cone: "M10 3h4l4 16H6L10 3zm-3 6h10M8.4 13h7.2M5 21h14",
	flag: "M5 21V3m0 1h12l-3 4 3 4H5",
	landmark: "M3 9l9-6 9 6H3zm2 1v8m4-8v8m4-8v8m4-8v8M3 21h18M3 18h18",
	trend: "M3 17l6-6 4 4 8-8m0 0h-5m5 0v5",
	globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18z",
	heart: "M12 21C7 16.5 3 13 3 8.8 3 6 5 4 7.5 4c1.7 0 3.2.9 4.5 2.6C13.3 4.9 14.8 4 16.5 4 19 4 21 6 21 8.8c0 4.2-4 7.7-9 12.2z",
	db: "M4 5c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
	clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zm0-13v5l3 2",
	share: "M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7M12 3v13m-4-4 4 4 4-4",
	radar: "M12 12 19 8M12 21a9 9 0 1 0-9-9m9 9a9 9 0 0 0 6.4-2.6L12 12",
	scan: "M4 8V5a1 1 0 0 1 1-1h3m8 0h3a1 1 0 0 1 1 1v3m0 8v3a1 1 0 0 1-1 1h-3m-8 0H5a1 1 0 0 1-1-1v-3M3 12h18",
	users: "M17 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2m7-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm10 10v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
};

export type IconName = keyof typeof PATHS | string;

export function Icon({
	name,
	size = 14,
	color,
	style,
}: {
	name: IconName;
	size?: number;
	color?: string;
	style?: CSSProperties;
}) {
	const d = PATHS[name] ?? PATHS.activity;
	return (
		<svg
			width={size}
			height={size}
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth="1.7"
			strokeLinecap="round"
			strokeLinejoin="round"
			style={{ color: color ?? "currentColor", flexShrink: 0, ...style }}
			aria-hidden
		>
			<path d={d} />
		</svg>
	);
}

/** Ícone + cor semântica por categoria de evento. */
export const CAT_ICON: Record<string, string> = {
	SECURITY: "shield",
	TRAFFIC: "cone",
	WEATHER: "wind",
	INFRASTRUCTURE: "zap",
	PROTEST: "flag",
	POLITICS: "landmark",
	ECONOMY: "trend",
	HEALTH: "heart",
	INTERNATIONAL: "globe",
	TECH: "db",
	EVENT: "clock",
	EMERGENCY: "flame",
	OTHER: "activity",
};

export function catColor(cat: string): string {
	return `var(--cat-${cat}, var(--tx2))`;
}
