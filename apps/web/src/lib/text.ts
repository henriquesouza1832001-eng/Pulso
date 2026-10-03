/** Minúsculas e sem acentos: "Alagamento em Belém" casa com "belem". */
export function fold(text: string): string {
	return text.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
}
