/** Barra de blocos de terminal: ██████░░░░ */
export function Blocks({
	value,
	max = 100,
	total = 20,
	color,
}: {
	value: number;
	max?: number;
	total?: number;
	color?: string;
}) {
	const filled = Math.max(0, Math.min(total, Math.round((value / max) * total)));
	return (
		<span className="blocks" style={color ? { color } : undefined}>
			<i>{"█".repeat(filled)}</i>
			<span style={{ color: "var(--ln1)" }}>{"░".repeat(total - filled)}</span>
		</span>
	);
}
