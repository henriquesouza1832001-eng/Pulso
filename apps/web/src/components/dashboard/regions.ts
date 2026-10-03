/** Regiões do IBGE → UFs. Usado nas abas do mapa e nos filtros do painel. */
export const REGIONS: Record<string, string[]> = {
	Norte: ["AC", "AP", "AM", "PA", "RO", "RR", "TO"],
	Nordeste: ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
	"Centro-Oeste": ["DF", "GO", "MT", "MS"],
	Sudeste: ["ES", "MG", "RJ", "SP"],
	Sul: ["PR", "RS", "SC"],
};

export const UF_LIST = Object.values(REGIONS).flat().sort();

export function regionOf(uf: string | null | undefined): string | null {
	if (!uf) return null;
	return Object.keys(REGIONS).find((r) => REGIONS[r].includes(uf)) ?? null;
}
