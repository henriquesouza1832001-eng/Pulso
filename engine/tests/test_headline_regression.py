"""Regressão do entendimento de notícias: manchetes reais-like rotuladas à mão.

Mede (1) categoria pelo keyword engine e (2) importância (impactante x ruído). É a nossa "régua":
ao ampliar vocabulário, rode e veja a taxa; quando errar, o caso entra aqui junto com a correção.
Não é aprendizado de máquina: o PULSO é baseado em regras transparentes e calibração (Brier) das previsões.
"""
from pulso_engine.processing.importance import assess
from pulso_engine.processing.keyword_engine import KeywordEngine

# (manchete, categoria esperada)
CATEGORY_CASES = [
    ("Chuva forte provoca alagamento e deslizamento em Petrópolis", "WEATHER"),
    ("INMET emite alerta laranja para onda de frio no Sul", "WEATHER"),
    ("Frente fria traz geada e neve para a serra catarinense", "WEATHER"),
    ("Apagão deixa 2 milhões de pessoas sem energia em São Paulo", "INFRASTRUCTURE"),
    ("Racionamento: moradores ficam sem água há três dias", "INFRASTRUCTURE"),
    ("Rompimento de adutora deixa bairros com falta de água", "INFRASTRUCTURE"),
    ("Greve de metroviários paralisa o metrô e causa lentidão no trânsito", "TRAFFIC"),
    ("Acidente grave bloqueia a Dutra no sentido Rio", "TRAFFIC"),
    ("Voos cancelados e atraso de voos no aeroporto de Guarulhos", "TRAFFIC"),
    ("Tiroteio durante megaoperação deixa mortos no Complexo da Maré", "SECURITY"),
    ("Latrocínio e roubo de cargas crescem no estado", "SECURITY"),
    ("Surto de sarampo é confirmado e Ministério da Saúde amplia vacinação", "HEALTH"),
    ("Casos de dengue e chikungunya lotam o pronto-socorro", "HEALTH"),
    ("Preço da gasolina sobe após reajuste da Petrobras", "ECONOMY"),
    ("Banco Central mantém a Selic e dólar fecha em alta", "ECONOMY"),
    ("Bandeira vermelha encarece a conta de luz em outubro", "ECONOMY"),
    ("Embaixada fecha as portas e crise diplomática se agrava", "INTERNATIONAL"),
    ("Itamaraty convoca embaixador após ruptura diplomática", "INTERNATIONAL"),
    ("STF decide sobre a candidatura e o Senado vota o impeachment", "POLITICS"),
    ("Pesquisa eleitoral mostra empate entre candidatos ao governo", "POLITICS"),
    ("Ataque hacker derruba sistemas e vazamento de dados expõe clientes", "TECH"),
    ("Instabilidade no Pix deixa bancos fora do ar", "TECH"),
    ("Manifestantes bloqueiam a avenida em protesto contra tarifa", "PROTEST"),
    ("Incêndio atinge prédio e bombeiros fazem resgate de moradores", "EMERGENCY"),
    ("Enem 2026 tem mais de 4 milhões de inscritos", "EVENT"),
    # manchetes reais de 2026-10-02 que o motor deixava escapar
    ("Casal é baleado em Satuba por criminosos em carro com adesivos de empresa de rastreio de motos", "SECURITY"),
    ("Empresário de 36 anos foi morto a tiros segundos após colocar filha no carro", "SECURITY"),
    ("Operação da Polícia Federal investiga envio e circulação de cédulas falsas em Alagoas", "SECURITY"),
    ("Falta de chuva faz Manaus ter setembro mais seco dos últimos quatro anos", "WEATHER"),
    ("Estrangeiro é a terceira vítima identificada entre mortos em queda de avião em MT", "EMERGENCY"),
    ("Carro atropela multidão e deixa diversos feridos", "TRAFFIC"),
    ("Produção de petróleo e gás natural no Brasil supera marca inédita, diz ANP", "ECONOMY"),
    ("Há vida após a recuperação judicial? Levantamento mostra que 77% das empresas quebram", "ECONOMY"),
    ("Distância entre Lula e Flávio Bolsonaro é de 3 pontos no 1º turno no Agregador de Pesquisas", "POLITICS"),
    ("Fachin aperta regras para evitar que pedidos ao Supremo sejam direcionados a ministros específicos", "POLITICS"),
    ("Trump diz que IA será grande tema de reunião com Xi Jinping", "INTERNATIONAL"),
    ("Nvidia anuncia aumento recorde em programa de recompra de ações", "TECH"),
]

# Conteúdo sem relevância para o Pulso: deve continuar SEM categoria (o vocabulário novo não pode trazer ruído).
NO_CATEGORY_CASES = [
    "Omelete de forno: 5 receitas ricas em proteínas para o almoço",
    "Mega-Sena 3062: aposta feita em Sergipe acerta quina e ganha prêmio de R$ 59 mil",
    "'Galinha Pintadinha - O filme' estreia nos cinemas da Paraíba",
    "Rapper Rick Ross é preso na Flórida por acusações de violência doméstica",
    "Nike acelera expansão de lojas no Brasil após renovar acordo com o Grupo SBF até 2034",
    "Taça das Favelas Feminina do ES realiza lançamento e sorteio das chaves neste sábado",
    "Rondoniense fica em 2º lugar no Miss Brasil Café 2027",
    "Promoção de Primavera do Steam começa com grandes jogos a preço de pinga",
]

# (texto, deve passar no filtro de importância?)
IMPORTANCE_CASES = [
    ("Enchente deixa 3 mortos e Defesa Civil emite alerta no Rio Grande do Sul", True),
    ("Deslizamento soterra casas em Petrópolis, bombeiros procuram desaparecidos", True),
    ("Tornado atinge cidade no Paraná e deixa feridos", True),
    ("Apagão atinge o Nordeste e deixa milhões sem energia", True),
    ("Surto de dengue: estado decreta situação de emergência", True),
    ("Rompimento de barragem provoca evacuação de comunidades", True),
    ("Ronaldinho Gaúcho casou e os famosos foram ao casamento", False),
    ("Fofoca: BBB tretou com influencer e o namoro acabou", False),
    ("Novela das nove termina com gol de placa no capítulo final", False),
    ("Bom dia, hoje o dia está lindo e a vida é bela", False),
    ("Casamento de celebridade lota igreja, famosos comentam", False),
    ("Inundações causam 70 mortes na Índia e no Nepal", True),  # importante, mas o filtro de país é outro (brazil_relevant)
]


def test_category_accuracy_is_high():
    kw = KeywordEngine()
    wrong = [(t, want, kw.classify(t)) for t, want in CATEGORY_CASES if kw.classify(t) != want]
    accuracy = 1 - len(wrong) / len(CATEGORY_CASES)
    assert accuracy >= 0.9, f"acurácia {accuracy:.0%}; erros: {wrong}"


def test_importance_separates_impact_from_noise():
    wrong = [(t, want, assess(t).score) for t, want in IMPORTANCE_CASES if assess(t).is_important() != want]
    assert not wrong, f"erros de importância: {wrong}"


def test_irrelevant_content_stays_uncategorized():
    kw = KeywordEngine()
    noisy = [(t, kw.classify(t)) for t in NO_CATEGORY_CASES if kw.classify(t) is not None]
    assert not noisy, f"ruído classificado: {noisy}"
