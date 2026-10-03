import type { PulsoEvent } from "@pulso/shared";
import type { Forecast, HistEntry } from "../components/sections/Forecasts";

/**
 * Dataset fictício para desenvolvimento/apresentação (VITE_DEMO=1).
 * Sempre exibido com o badge "DEMO DATA" no header. Nunca vai para produção.
 */

const min = (n: number) => new Date(Date.now() - n * 60_000).toISOString();

function ev(
	id: string,
	title: string,
	category: PulsoEvent["category"],
	status: PulsoEvent["status"],
	lon: number,
	lat: number,
	state: string,
	city: string,
	severity: number,
	confidence: number,
	pulse: number,
	alert_level: PulsoEvent["alert_level"],
	signals: number,
	sources: number,
	summary: string,
): PulsoEvent {
	return {
		event_id: id,
		title,
		summary,
		category,
		status,
		latitude: lat,
		longitude: lon,
		geo_precision: "CITY",
		geo_confidence: 80,
		state,
		city,
		severity,
		confidence,
		pulse,
		alert_level,
		score_breakdown: [
			{ key: "confidence", label: "Confiança", points: Math.round(confidence * 0.15) },
			{ key: "sources", label: "Diversidade de fontes", points: Math.min(15, sources * 3) },
			{ key: "velocity", label: "Velocidade de sinais", points: Math.round(pulse * 0.14) },
			{ key: "anomaly", label: "Anomalia vs. baseline", points: Math.round(pulse * 0.11) },
			{ key: "severity", label: "Severidade", points: Math.round(severity * 0.18) },
		],
		signal_count: signals,
		source_count: sources,
		detected_at: min(52),
		updated_at: min(Math.max(2, Math.round(pulse / 3))),
	};
}

export const DEMO_EVENTS: PulsoEvent[] = [
	ev("demo-1", "Incêndio em depósito atinge via Anchieta", "EMERGENCY", "CONFIRMED", -46.42, -23.85, "SP", "Cubatão", 71, 88, 84, 4, 26, 4,
		"fumaça visível desde 22:12. bombeiros com 12 viaturas e tráfego bloqueado no sentido baixada, km 61."),
	ev("demo-2", "Interdição total da ponte Rio-Niterói", "TRAFFIC", "CONFIRMED", -43.16, -22.9, "RJ", "Rio de Janeiro", 58, 97, 79, 4, 19, 5,
		"prf interditou nos dois sentidos após acidente múltiplo no km 12. retenção de 5 km na entrada."),
	ev("demo-3", "Concentração crescente na Esplanada", "PROTEST", "DEVELOPING", -47.93, -15.78, "DF", "Brasília", 64, 61, 57, 3, 14, 3,
		"relatos de mobilização para ato previsto. defesa civil confirmou bloqueio parcial. sem cobertura da imprensa ainda."),
	ev("demo-4", "Acidente com caminhão na BR-381", "TRAFFIC", "CONFIRMED", -43.94, -19.92, "MG", "Betim", 35, 98, 62, 3, 9, 4,
		"faixa direita interditada no km 412, sentido BH. retenção de 14 km."),
	ev("demo-5", "Alagamento na orla após temporal", "WEATHER", "STABLE", -38.51, -12.97, "BA", "Salvador", 52, 74, 54, 3, 22, 6,
		"acumulado alto em 3h. trânsito lento em toda a orla e ponto de apoio montado."),
	ev("demo-6", "Sobrecarga no sistema elétrico", "INFRASTRUCTURE", "DEVELOPING", -44.3, -2.53, "MA", "São Luís", 47, 44, 41, 3, 11, 2,
		"relatos repetidos de queda parcial em bairros da região metropolitana. distribuidora não confirmou."),
	ev("demo-7", "Conflito reportado no centro", "SECURITY", "DETECTED", -48.5, -1.45, "PA", "Belém", 55, 38, 39, 3, 7, 2,
		"vídeos circulando em redes sociais. nenhuma confirmação oficial até o momento. confiança baixa por design."),
	ev("demo-8", "Rajadas e aviso laranja no litoral norte", "WEATHER", "CONFIRMED", -46.31, -24.03, "SP", "São Sebastião", 44, 92, 48, 2, 8, 3,
		"inmet mantém aviso laranja até 06h. acumulado de 62 mm em 3h."),
	ev("demo-9", "Fluxo elevado na Marginal Tietê", "TRAFFIC", "STABLE", -46.68, -23.51, "SP", "São Paulo", 22, 85, 31, 2, 6, 2,
		"velocidade média abaixo de 20 km/h nos dois sentidos. dentro do padrão de pico."),
	ev("demo-10", "Queda de árvore bloqueia via", "INFRASTRUCTURE", "RESOLVING", -49.27, -25.43, "PR", "Curitiba", 18, 90, 22, 1, 3, 2,
		"equipe no local, desvio pelo sentido oposto. normalização prevista em 40 min."),
];

export const DEMO_FORECASTS: Forecast[] = [
	{ q: "o PULSO de DF alcança N4 nas próximas 6h?", yes: 71, drivers: "14 sinais convergindo" },
	{ q: "temporal severo atinge a GRBS/SP até 06h?", yes: 68, drivers: "inmet + 2 fontes" },
	{ q: "o PULSO nacional sai de N3 nas próximas 24h?", yes: 34, drivers: "depende do eixo SP·RJ" },
];

export const DEMO_HISTORY: HistEntry[] = [
	{ date: "28/09", text: "APAGÃO EM MANAUS/AM · PULSO 4 POR 3H12 · 62 SINAIS · CONF 91%", level: 4 },
	{ date: "21/09", text: "ATOS NACIONAIS · SINAIS EM 24 UFS · PICO 17:40", level: 4 },
	{ date: "14/09", text: "TEMPORAL NO LITORAL NORTE/SP · 118 MM ACUMULADOS", level: 3 },
];

export const DEMO_CAMERAS = [
	{ id: "CCT-044", label: "Via Anchieta km 61", city: "Cubatão", state: "SP", status: "CRÍTICO" as const },
	{ id: "CCT-112", label: "Esplanada Eixo Monumental", city: "Brasília", state: "DF", status: "ELEVADO" as const },
	{ id: "CCT-007", label: "Ponte Rio-Niterói acesso", city: "Rio de Janeiro", state: "RJ", status: "CRÍTICO" as const },
	{ id: "CCT-231", label: "Av. Paulista c/ R. Augusta", city: "São Paulo", state: "SP", status: "ELEVADO" as const },
];

/** Sinais fictícios exibidos no detalhe de eventos demo (ids demo-*). */
export const DEMO_SIGNALS: Record<string, Array<{ source: string; cls: string; title: string }>> = {
	"demo-1": [
		{ source: "G1", cls: "NEWS_HIGH", title: "Incêndio atinge depósito em Cubatão" },
		{ source: "BOMBEIROS/SP", cls: "OFFICIAL", title: "Operação com 12 viaturas em curso" },
		{ source: "CAM/CCT-044", cls: "TRAFFIC_PROVIDER", title: "Fumaça visível na via Anchieta" },
		{ source: "X/@RADA-SP", cls: "SOCIAL", title: "\"rolou uma fumaça enorme na serra\"" },
	],
	"demo-2": [
		{ source: "PRF", cls: "OFFICIAL", title: "Interdição total, km 12 sentido RJ" },
		{ source: "CET-RIO", cls: "OFFICIAL", title: "Fila de 5 km no acesso" },
		{ source: "G1", cls: "NEWS_HIGH", title: "Acidente múltiplo na ponte" },
	],
	default: [
		{ source: "X/@RADA", cls: "SOCIAL", title: "Relato compatível na região" },
		{ source: "INMET", cls: "OFFICIAL", title: "Boletim regional atualizado" },
	],
};
