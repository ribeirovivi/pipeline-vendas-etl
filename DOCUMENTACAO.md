# Documentação técnica — Pipeline ETL de vendas (Data Warehouse em estrela)

> Complementa o [README](README.md). Aqui estão o desenho, o dicionário de dados,
> as regras, as decisões, os limites e o caminho de evolução.

## 1. Objetivo

Demonstrar, de ponta a ponta, o ciclo de um pipeline de dados confiável:
**extrair → validar → transformar → carregar → reconciliar → reportar**, entregando
um *Data Warehouse* dimensional pronto para consultas analíticas.

| Item | Valor |
|---|---|
| Linguagem | Python 3.9+ (somente biblioteca padrão) |
| Armazenamento | SQLite (arquivo único) e Excel (`.xlsx`) |
| Entrada | CSV de vendas (+ CSV de produtos) |
| Saída | Banco SQLite, planilha Excel, relatório `.md`, `qualidade.json`, `rejeitados.csv` |
| Testes | 10 (`unittest`) |

## 2. Fluxo

```
vendas_brutas.csv ─┐
produtos.csv ──────┴► extrair ► limpar(validar + deduplicar) ► transformar ► carregar ► relatórios
                                       │                                         │
                                       └─► rejeitados.csv (com o motivo)          └─► vendas_dw.sqlite / .xlsx
```

1. **Extrair** (`pipeline.extrair`): lê o CSV como lista de dicionários (tudo texto).
2. **Limpar** (`pipeline.limpar`): descarta duplicados (mantém a 1ª ocorrência de cada
   `id_pedido`) e aplica 8 regras de qualidade; o que falha vai para *rejeitados* com a
   lista de regras violadas.
3. **Transformar** (`pipeline.transformar`): converte tipos, calcula valores e monta as
   dimensões e o fato.
4. **Carregar** (`pipeline.carregar`): recria o esquema e insere tudo **em uma única
   transação**.
5. **Reconciliar** (`run_pipeline.main`): confere
   `lidas = carregadas + rejeitadas + duplicadas`; se não bater, a execução falha.
6. **Reportar**: `qualidade.json`, `relatorio.md`, `vendas_dw.xlsx`, `rejeitados.csv`.

## 3. Dicionário de dados

### 3.1 Entrada — `vendas_brutas.csv`

| Coluna | Tipo (texto) | Descrição |
|---|---|---|
| `id_pedido` | texto | Identificador do pedido (chave) |
| `data_pedido` | texto | `AAAA-MM-DD` **ou** `DD/MM/AAAA` (dois formatos de propósito) |
| `id_cliente`, `nome_cliente` | texto | Cliente |
| `segmento` | texto | Varejo, Corporativo ou Governo |
| `uf` | texto | Unidade da federação (obrigatória) |
| `id_produto` | texto | Deve existir em `produtos.csv` |
| `quantidade` | inteiro (texto) | > 0 |
| `preco_unitario` | decimal (texto) | > 0 |
| `desconto_pct` | decimal (texto) | 0 a 100 |
| `canal` | texto | Loja online, Aplicativo, Televendas ou Parceiros |

### 3.2 Saída — esquema estrela (SQLite)

| Tabela | Grão / chave | Colunas |
|---|---|---|
| `fato_vendas` | 1 linha por pedido (`id_pedido`) | `id_data`, `id_cliente`, `id_produto`, `canal`, `quantidade`, `preco_unitario`, `desconto_pct`, `valor_bruto`, `valor_desconto`, `valor_liquido` |
| `dim_cliente` | `id_cliente` | `nome`, `segmento`, `uf` |
| `dim_produto` | `id_produto` | `nome`, `categoria`, `preco_lista` |
| `dim_tempo` | `id_data` (AAAAMMDD) | `data`, `ano`, `mes`, `trimestre`, `dia_semana` |

**Cálculos**

```
valor_bruto    = quantidade × preco_unitario
valor_desconto = valor_bruto × desconto_pct / 100
valor_liquido  = valor_bruto − valor_desconto
```

**Integridade:** chaves estrangeiras da fato para as dimensões (`PRAGMA foreign_keys=ON`),
`CHECK` em quantidade (> 0), preço (> 0) e desconto (0–100), índices por data e produto.

## 4. Regras de qualidade

| # | Regra (código) | Condição para REJEITAR |
|---|---|---|
| 1 | `id_pedido_vazio` | identificador em branco |
| 2 | `data_invalida` | data inexistente (ex.: 31/02) ou fora dos dois formatos |
| 3 | `cliente_vazio` | `id_cliente` em branco |
| 4 | `uf_vazia` | UF em branco |
| 5 | `produto_desconhecido` | produto fora do cadastro |
| 6 | `quantidade_invalida` | não numérica ou ≤ 0 |
| 7 | `preco_invalido` | não numérico ou ≤ 0 |
| 8 | `desconto_invalido` | não numérico ou fora de 0–100 |
| — | duplicidade | mesmo `id_pedido` já visto (descartado, contado à parte) |

Um registro pode violar várias regras; por isso a soma das ocorrências por regra
(265) é maior que o número de registros rejeitados (259).

## 5. Resultado de referência (seed 42, 5.000 linhas + 100 duplicatas)

| Métrica | Valor |
|---|---|
| Linhas lidas | 5.100 |
| Duplicados removidos | 100 |
| Rejeitados | 259 |
| Carregados | 4.741 (92,96 %) |
| Tempo | ≈ 0,3 s |

Consultas analíticas entregues no relatório: receita líquida por mês, top 5 produtos,
receita e ticket médio por canal e receita por segmento de cliente.

## 6. Estrutura do código

| Arquivo | Responsabilidade |
|---|---|
| `run_pipeline.py` | Interface de linha de comando, orquestra as etapas, consultas e relatórios |
| `etl/gerar_dados.py` | Gera dados brutos "sujos", determinísticos por `seed` |
| `etl/pipeline.py` | `extrair`, `validar`, `limpar`, `transformar`, `carregar` e o `SCHEMA` |
| `etl/xlsx_simples.py` | Escritor de `.xlsx` com a biblioteca padrão (negrito, filtro, painel congelado) |
| `tests/test_pipeline.py` | 10 testes: regras, deduplicação, cálculos, ponta a ponta, CLI e Excel |
| `dados/`, `exemplo_saida/` | Entrada e resultado de referência |

## 7. Opções de execução

| Opção | Efeito |
|---|---|
| `--linhas N` | Quantidade de linhas geradas (padrão 5000) |
| `--seed N` | Semente aleatória (padrão 42) |
| `--saida PASTA` | Pasta de saída (padrão `saida`) |
| `--entrada ARQ.csv` | Usa um CSV próprio em vez de gerar (exige `produtos.csv` ao lado, ou `--produtos`) |

Código de saída: `0` sucesso; `1` arquivo de entrada inexistente.

## 8. Decisões de projeto (e por quê)

| Decisão | Motivo |
|---|---|
| Rejeitar em vez de "corrigir" | Corrigir sem a origem esconde o problema; rejeitar com motivo permite tratar na fonte |
| Reconciliação obrigatória | Garante que nenhuma linha "some" silenciosamente |
| Carga idempotente (recria e carrega numa transação) | Reexecutar não duplica nem deixa estado parcial |
| `seed` fixa | Resultados reproduzíveis para testes e comparação |
| Só biblioteca padrão | Roda em qualquer máquina, sem instalar nada |
| Modelo estrela | Consultas simples e rápidas; padrão de mercado para BI |
| UTF-8 com BOM nos CSVs | O Excel abre com acentos corretos |

## 9. Limitações conhecidas

- **Carga completa:** a cada execução o DW é recriado (não incremental). O projeto
  *Lakehouse medalhão* demonstra a carga incremental.
- **Memória:** os registros são processados em listas; para milhões de linhas seria
  preciso processar em blocos (*chunks*) ou usar um motor distribuído.
- **Dimensões sem histórico:** `dim_cliente` guarda a 1ª ocorrência (sem SCD). O
  *Lakehouse* implementa SCD tipo 2.
- **SQLite:** ótimo para demonstração; em produção usaria um banco/DW corporativo.
- **Dados sintéticos:** gerados por programa, não são dados reais de nenhuma empresa.

## 10. Evolução natural (produção)

1. Trocar `extrair` por leitura de uma fonte real (arquivo em armazenamento, banco, API).
2. Trocar `carregar` por *upsert*/`MERGE` em um DW (ex.: Databricks/Delta, SQL Server).
3. Orquestrar com um agendador (ex.: Airflow, Azure Data Factory).
4. Publicar as métricas de qualidade em um painel e alertar quando a taxa de
   aprovação cair abaixo de um limite.
5. Rodar os testes em uma esteira de integração contínua.

## 11. Como validar

```bash
python -m unittest discover -s tests -v          # 10 testes
python run_pipeline.py --entrada dados/vendas_brutas.csv --saida conferencia
# compare conferencia/qualidade.json com exemplo_saida/qualidade.json (mesmos números)
```
