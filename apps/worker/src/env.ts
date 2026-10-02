export interface Bindings {
	DB: D1Database;
	ALLOWED_ORIGINS: string;
	/** Segredo: autoriza o Python Engine a gravar via /api/ingest. */
	INGEST_TOKEN?: string;
}
export type AppEnv = { Bindings: Bindings };
