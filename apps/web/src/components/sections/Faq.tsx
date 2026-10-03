/**
 * FAQ + disclaimer operacional — o rodapé editorial do pizzint:
 * perguntas diretas, resposta curta, link de retorno ao vivo.
 */
const QA: Array<[string, string]> = [
	[
		"O QUE É O PULSO?",
		"um índice independente que mede a intensidade de sinais públicos no brasil: notícias, boletins oficiais, trânsito, clima e relatos abertos, agregados por um motor que agrupa sinais convergentes em eventos.",
	],
	[
		"PULSO ALTO SIGNIFICA PERIGO?",
		"não. o índice mede volume e velocidade de sinais, não probabilidade de dano e não veracidade. um evento pode ter pulso alto e se confirmar inofensivo, e vice-versa.",
	],
	[
		"QUAL A DIFERENÇA ENTRE SEVERIDADE E CONFIANÇA?",
		"severidade é o impacto potencial do evento; confiança é quanto os sinais independentes sustentam que ele existe de fato. os dois são exibidos separados, sempre.",
	],
	[
		"QUEM SÃO AS FONTES?",
		"veículos de notícia, órgãos oficiais (defesa civil, inmet, prf), provedores de trânsito e relatos públicos abertos. toda alegação permanece ligada à fonte original, clicável no dossiê de cada evento.",
	],
	[
		"VOCÊS MONITORAM PESSOAS?",
		"não. nenhum dado pessoal é coletado. câmeras exibidas são sensores ambientais públicos (vias, praças), nunca vigilância de indivíduos.",
	],
];

export function Faq() {
	return (
		<div className="faq">
			{QA.map(([q, a]) => (
				<details key={q} className="faq-item">
					<summary>{q}</summary>
					<p>{a}</p>
				</details>
			))}

			<div className="disclaimer">
				<h3>DISCLAIMER OPERACIONAL</h3>
				<p>
					o pulso é uma ferramenta de leitura de sinais públicos em tempo real. não substitui
					fontes oficiais de emergência, não apura fatos e não faz previsão garantida. em caso
					de emergência real, procure defesa civil e autoridades locais. monitore os sinais
					com responsabilidade.
				</p>
			</div>

			<a className="back-live" href="#feed">
				↑ VOLTAR AOS DADOS AO VIVO
			</a>
		</div>
	);
}
