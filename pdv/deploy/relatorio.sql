-- Relatório do piloto (DEC-10): pedidos por dia e restaurante, sem dados pessoais.
-- Parâmetro: :dias (quantos dias para trás, contando hoje no fuso de cada restaurante).
\pset footer off
\echo
\echo '== Pedidos por dia'
SELECT r.nome AS restaurante,
       p.data_local AS dia,
       count(*) AS pedidos,
       count(*) FILTER (WHERE p.status = 'Finalizado') AS finalizados,
       count(*) FILTER (WHERE p.status = 'Cancelado') AS cancelados,
       count(*) FILTER (WHERE p.status IN ('Recebido', 'Em preparo', 'Pronto')) AS em_aberto,
       count(*) FILTER (WHERE p.tipo = 'entrega') AS entregas,
       round(avg(p.total_centavos) FILTER (WHERE p.status <> 'Cancelado') / 100.0, 2) AS ticket_medio_reais,
       round(sum(p.total_centavos) FILTER (WHERE p.status <> 'Cancelado') / 100.0, 2) AS vendido_reais
FROM pedido p
JOIN restaurante r ON r.id = p.restaurante_id
WHERE p.data_local > (now() AT TIME ZONE r.fuso)::date - :dias
GROUP BY r.nome, p.data_local
ORDER BY r.nome, p.data_local;

\echo
\echo '== Tempos (mediana e 90% dos pedidos, em minutos)'
SELECT r.nome AS restaurante,
       count(*) FILTER (WHERE p.em_preparo_em IS NOT NULL) AS com_preparo,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM p.em_preparo_em - p.criado_em) / 60)::numeric, 1) AS ate_preparo_med,
       round(percentile_cont(0.9) WITHIN GROUP (ORDER BY extract(epoch FROM p.em_preparo_em - p.criado_em) / 60)::numeric, 1) AS ate_preparo_p90,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM p.pronto_em - p.em_preparo_em) / 60)::numeric, 1) AS preparo_med,
       round(percentile_cont(0.9) WITHIN GROUP (ORDER BY extract(epoch FROM p.pronto_em - p.em_preparo_em) / 60)::numeric, 1) AS preparo_p90,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM p.finalizado_em - p.pronto_em) / 60)::numeric, 1) AS pronto_ate_final_med
FROM pedido p
JOIN restaurante r ON r.id = p.restaurante_id
WHERE p.data_local > (now() AT TIME ZONE r.fuso)::date - :dias
GROUP BY r.nome
ORDER BY r.nome;

\echo
\echo '== Pedidos por hora do dia (horário do restaurante)'
SELECT r.nome AS restaurante,
       extract(hour FROM p.criado_em AT TIME ZONE r.fuso)::int AS hora,
       count(*) AS pedidos
FROM pedido p
JOIN restaurante r ON r.id = p.restaurante_id
WHERE p.data_local > (now() AT TIME ZONE r.fuso)::date - :dias
GROUP BY r.nome, hora
ORDER BY r.nome, hora;

\echo
\echo '== Motivos de cancelamento'
SELECT r.nome AS restaurante, p.motivo_cancelamento AS motivo, count(*) AS vezes
FROM pedido p
JOIN restaurante r ON r.id = p.restaurante_id
WHERE p.status = 'Cancelado'
  AND p.data_local > (now() AT TIME ZONE r.fuso)::date - :dias
GROUP BY r.nome, p.motivo_cancelamento
ORDER BY r.nome, vezes DESC;

\echo
\echo '== Itens mais pedidos'
SELECT r.nome AS restaurante, i.nome AS item, sum(i.quantidade) AS unidades
FROM pedido_item i
JOIN pedido p ON p.id = i.pedido_id
JOIN restaurante r ON r.id = p.restaurante_id
WHERE p.status <> 'Cancelado'
  AND p.data_local > (now() AT TIME ZONE r.fuso)::date - :dias
GROUP BY r.nome, i.nome
ORDER BY r.nome, unidades DESC
LIMIT 30;

\echo
\echo '== Conexão do WhatsApp'
SELECT r.nome AS restaurante, coalesce(c.status, 'nunca conectado') AS status, c.atualizado_em
FROM restaurante r
LEFT JOIN conexao_whatsapp c ON c.restaurante_id = r.id
ORDER BY r.nome;
