export interface Bindings {
	DB: D1Database;
	ALLOWED_ORIGINS: string;
	/** Segredo: autoriza o Python Engine a gravar via /api/ingest. */
	INGEST_TOKEN?: string;
	/** Segredo: token fino do GitHub usado pelo Cron Trigger para acionar a coleta. */
	GH_DISPATCH_TOKEN?: string;
	/** "dono/repositório" do GitHub. */
	GITHUB_REPO: string;
}
export type AppEnv = { Bindings: Bindings };
