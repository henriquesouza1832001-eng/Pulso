export interface Bindings {
	DB: D1Database;
	/** "turso" troca o D1 pelo Turso (lib/turso.ts) sem mudar as rotas; qualquer outro valor mantém o D1. */
	DB_BACKEND?: string;
	/** Segredos do Turso (`wrangler secret put`): URL libsql:// do banco e token DO BANCO. */
	TURSO_URL?: string;
	TURSO_TOKEN?: string;
	ALLOWED_ORIGINS: string;
	/** Segredo: autoriza o Python Engine a gravar via /api/ingest. */
	INGEST_TOKEN?: string;
	/** Segredo: token fino do GitHub usado pelo Cron Trigger para acionar a coleta. */
	GH_DISPATCH_TOKEN?: string;
	/** "dono/repositório" do GitHub. */
	GITHUB_REPO: string;
}
export type AppEnv = { Bindings: Bindings; Variables: { requestId: string } };
