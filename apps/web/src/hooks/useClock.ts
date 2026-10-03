import { useEffect, useState } from "react";
import { pad2 } from "../lib/format";

export interface Clock {
	/** "22:41:03" (Brasília) */
	br: string;
	/** "01:41:03Z" */
	z: string;
	/** "QUI 02 OUT 2026" */
	date: string;
}

const DIAS = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"];
const MES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"];

function now(): Clock {
	const d = new Date();
	const b = new Date(d.toLocaleString("en-US", { timeZone: "America/Sao_Paulo" }));
	return {
		br: `${pad2(b.getHours())}:${pad2(b.getMinutes())}:${pad2(b.getSeconds())}`,
		z: `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}:${pad2(d.getUTCSeconds())}Z`,
		date: `${DIAS[b.getDay()]} ${pad2(b.getDate())} ${MES[b.getMonth()]} ${b.getFullYear()}`,
	};
}

export function useClock(): Clock {
	const [c, setC] = useState<Clock>(now);
	useEffect(() => {
		const id = setInterval(() => setC(now()), 1000);
		return () => clearInterval(id);
	}, []);
	return c;
}
