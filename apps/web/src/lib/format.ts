import type { AlertLevel, Category, EventStatus, SourceClass } from "@pulso/shared";

export const LEVEL_PT: Record<AlertLevel, string> = {
	1: "NORMAL",
	2: "ATENÇÃO",
	3: "ELEVADO",
	4: "CRÍTICO",
	5: "EMERGÊNCIA",
};

export const CATEGORY_PT: Record<Category, string> = {
	SECURITY: "SEGURANÇA",
	TRAFFIC: "TRÂNSITO",
	WEATHER: "CLIMA",
	INFRASTRUCTURE: "INFRA",
	PROTEST: "MANIFESTAÇÃO",
	POLITICS: "POLÍTICA",
	ECONOMY: "ECONOMIA",
	HEALTH: "SAÚDE",
	INTERNATIONAL: "INTERNACIONAL",
	TECH: "TECNOLOGIA",
	EVENT: "EVENTO",
	EMERGENCY: "EMERGÊNCIA",
	OTHER: "OUTRO",
};

export const STATUS_PT: Record<EventStatus, string> = {
	DETECTED: "DETECTADO",
	DEVELOPING: "EM DESENVOLVIMENTO",
	CONFIRMED: "CONFIRMADO",
	STABLE: "ESTÁVEL",
	RESOLVING: "RESOLVENDO",
	RESOLVED: "RESOLVIDO",
	DISPUTED: "EM DISPUTA",
};

export const SOURCE_CLASS_PT: Record<SourceClass, string> = {
	OFFICIAL: "OFICIAL",
	NEWS_HIGH: "NOTÍCIAS NAC.",
	NEWS_REGIONAL: "NOTÍCIAS REG.",
	TRAFFIC_PROVIDER: "TRÂNSITO",
	SOCIAL_VERIFIED: "SOCIAL VERIF.",
	SOCIAL: "SOCIAL",
	UNKNOWN: "DESCONHECIDO",
};

/** "22:41:03" no fuso de Brasília (UTC-3, sem DST desde 2019). */
export function brTime(iso: string): string {
	return new Date(iso).toLocaleTimeString("pt-BR", {
		timeZone: "America/Sao_Paulo",
		hour12: false,
	});
}

/** "01:41:03Z" */
export function zTime(d: Date): string {
	const p = (n: number) => String(n).padStart(2, "0");
	return `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}Z`;
}

/** "há 12s" / "há 3min", sem atualizar sozinho. */
export function ago(iso: string, now = Date.now()): string {
	const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
	if (s < 60) return `há ${s}s`;
	if (s < 3600) return `há ${Math.floor(s / 60)}min`;
	return `há ${Math.floor(s / 3600)}h`;
}

/** ID curto de exibição: EVT-8821 no espírito do pizzint. */
export function evtId(id: string): string {
	const tail = id.replace(/[^0-9a-z]/gi, "").slice(-4);
	return `EVT-${(tail || "0000").toUpperCase()}`;
}

export function pad2(n: number): string {
	return String(n).padStart(2, "0");
}
