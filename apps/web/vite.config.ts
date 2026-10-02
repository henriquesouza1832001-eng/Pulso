import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
	plugins: [react()],
	server: {
		port: 5173,
		// Em dev o front chama /api e o Vite repassa ao Worker local (wrangler dev).
		proxy: { "/api": "http://localhost:8787" },
	},
});
