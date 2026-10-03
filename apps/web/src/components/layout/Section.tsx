import type { ReactNode } from "react";

/**
 * Seção no molde do pizzint: kicker azul + H2 + descrição + CTA de fechamento.
 * Toda seção abre e fecha com texto/link, nunca com chip técnico.
 */
export function Section({
	id,
	kicker,
	title,
	desc,
	cta,
	ctaHref,
	children,
	last,
}: {
	id?: string;
	kicker: string;
	title: string;
	desc?: string;
	cta?: string;
	ctaHref?: string;
	children: ReactNode;
	last?: boolean;
}) {
	return (
		<section className="sec" id={id} style={last ? { borderBottom: 0 } : undefined}>
			<div className="sechead">
				<span className="kicker">{kicker.toUpperCase()}</span>
				<h2>{title.toUpperCase()}</h2>
				{desc && <p className="desc">{desc}</p>}
			</div>
			{children}
			{cta && ctaHref && (
				<a className="seccta" href={ctaHref}>
					{cta} <span aria-hidden>→</span>
				</a>
			)}
		</section>
	);
}
