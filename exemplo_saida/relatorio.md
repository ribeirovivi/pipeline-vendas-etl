# Relatório do pipeline de vendas

## Qualidade dos dados

| Métrica | Valor |
|---|---|
| Linhas lidas | 5100 |
| Duplicados removidos | 100 |
| Rejeitados (regras) | 259 |
| Carregados no DW | 4741 |
| Taxa de aprovação | 92.96% |


### Violações por regra

| Regra | Ocorrências |
|---|---|
| quantidade_invalida | 75 |
| desconto_invalido | 50 |
| data_invalida | 50 |
| uf_vazia | 50 |
| preco_invalido | 40 |


## Receita líquida por mês

| mes | pedidos | receita |
|---|---|---|
| 2025-01 | 388 | 1088355.9 |
| 2025-02 | 358 | 1096458.98 |
| 2025-03 | 384 | 1172913.89 |
| 2025-04 | 388 | 1130307.7 |
| 2025-05 | 412 | 1275832.5 |
| 2025-06 | 395 | 1355303.7 |
| 2025-07 | 392 | 1230231.77 |
| 2025-08 | 426 | 1163690.63 |
| 2025-09 | 388 | 1100191.4 |
| 2025-10 | 385 | 1124617.24 |
| 2025-11 | 419 | 1257375.31 |
| 2025-12 | 406 | 1076149.63 |


## Top 5 produtos por receita

| nome | categoria | unidades | receita |
|---|---|---|---|
| Notebook 14 | Informática | 1802 | 5916755.48 |
| Mesa Ajustável | Escritório | 1777 | 3140707.5 |
| Cadeira Ergonômica | Escritório | 1706 | 2069482.5 |
| Monitor 24 | Informática | 1781 | 1499666.85 |
| Teclado Mecânico | Periféricos | 1837 | 501860.63 |


## Receita e ticket médio por canal

| canal | pedidos | receita | ticket_medio |
|---|---|---|---|
| Loja online | 1158 | 3670154.29 | 3169.39 |
| Parceiros | 1204 | 3661444.47 | 3041.07 |
| Aplicativo | 1171 | 3427144.81 | 2926.68 |
| Televendas | 1208 | 3312685.08 | 2742.29 |


## Receita por segmento de cliente

| segmento | clientes | receita |
|---|---|---|
| Governo | 140 | 4917856.37 |
| Varejo | 139 | 4791938.51 |
| Corporativo | 121 | 4361633.77 |
