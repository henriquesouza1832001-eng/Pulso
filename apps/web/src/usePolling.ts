import { useEffect, useState } from "react";

/** Busca periódica leve. Mantém o último dado se uma chamada falhar. */
export function usePolling<T>(fn: () => Promise<T>, ms: number) {
	const [data, setData] = useState<T | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [updatedAt, setUpdatedAt] = useState<number | null>(null);

	useEffect(() => {
		let alive = true;
		const tick = async () => {
			try {
				const d = await fn();
				if (!alive) return;
				setData(d);
				setError(null);
				setUpdatedAt(Date.now());
			} catch (e) {
				if (alive) setError(e instanceof Error ? e.message : "erro");
			}
		};
		tick();
		const id = setInterval(tick, ms);
		return () => {
			alive = false;
			clearInterval(id);
		};
	}, [fn, ms]);

	return { data, error, updatedAt };
}
