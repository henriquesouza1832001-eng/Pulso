import type { AlertLevel } from "@pulso/shared";
import { LEVEL_PT } from "../../lib/format";

export function LevelTag({ level, compact }: { level: AlertLevel; compact?: boolean }) {
	return (
		<span className={`lvtag n${level}`}>
			N{level}
			{!compact && ` ${LEVEL_PT[level]}`}
		</span>
	);
}

export function levelVar(level: AlertLevel): string {
	return `var(--lv${level})`;
}
