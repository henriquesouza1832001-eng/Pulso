# Migrations pendentes para o D1

`0005_write_budget.sql` já foi aplicada no **Turso** (que hoje é o banco ativo) e fica aqui, fora de `migrations/`, porque o
deploy aplica a pasta `migrations/` no D1 e o D1 está sem cota de escrita até 00:00 UTC (a migration falharia e travaria o deploy).
Quando for hora de separar os bancos (D1 de volta como banco quente), mover o arquivo de volta para `database/migrations/`.
