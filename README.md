# Pipeline ETL de vendas com Data Warehouse em estrela

Pipeline de dados de ponta a ponta: gera um CSV bruto "sujo", aplica regras de
qualidade, transforma e carrega um **modelo estrela** em SQLite, com
**reconciliação** de linhas e relatório de qualidade. Só biblioteca padrão do
Python 3.9+ (nada para instalar).

## Executar

```bash
python run_pipeline.py                         # 5.000 linhas, seed 42
python run_pipeline.py --linhas 20000 --seed 7 --saida resultado
python run_pipeline.py --entrada dados/vendas_brutas.csv   # usa um CSV (seu ou o de exemplo)
python -m unittest discover -s tests -v        # 10 testes
```

Saídas em `saida/`: `vendas_dw.sqlite` (banco), `vendas_dw.xlsx` (Excel, todas as
tabelas + relatório), `qualidade.json`, `relatorio.md`, `rejeitados.csv` e `bruto/`
(CSVs de origem, quando gerados).

## Dados de exemplo (para conferir e testar)

| Pasta / arquivo | O que é |
|---|---|
| `dados/vendas_brutas.csv` | 5.100 linhas **brutas e "sujas"** (entrada do pipeline) |
| `dados/produtos.csv` | cadastro de 8 produtos |
| `dados/vendas_brutas.xlsx` | os mesmos dados em Excel (abas `vendas_brutas` e `produtos`) |
| `exemplo_saida/vendas_dw.sqlite` | Data Warehouse resultante (abra com DB Browser for SQLite) |
| `exemplo_saida/vendas_dw.xlsx` | resultado em Excel: qualidade, consultas, fato, dimensões e rejeitados |
| `exemplo_saida/qualidade.json`, `relatorio.md`, `rejeitados.csv` | relatórios da execução de referência |

**Para testar com os seus dados:** abra `dados/vendas_brutas.csv` no Excel, altere
ou acrescente linhas (mantenha as colunas), salve como *CSV UTF-8* e execute
`python run_pipeline.py --entrada seu_arquivo.csv`. Rodar com o CSV de exemplo
reproduz exatamente `exemplo_saida/` (conferido).

## Arquitetura

```
CSV bruto ──► extrair ──► validar/limpar ──► transformar ──► carregar ──► relatórios
              (csv)       dedup + 8 regras    tipos, valores   SQLite      qualidade.json
                          rejeitados.csv      dims + fato      estrela     relatorio.md
```

Modelo: `fato_vendas` (grão = pedido) + `dim_cliente`, `dim_produto`, `dim_tempo`,
com chaves estrangeiras, `CHECK` de domínio e índices.

## Regras de qualidade

| Regra | Descrição |
|---|---|
| `data_invalida` | data inexistente ou fora de AAAA-MM-DD / DD/MM/AAAA |
| `uf_vazia` | UF obrigatória |
| `quantidade_invalida` | quantidade inteira > 0 |
| `preco_invalido` | preço unitário > 0 |
| `desconto_invalido` | desconto entre 0 e 100 |
| `produto_desconhecido` | produto precisa existir no cadastro |
| `cliente_vazio`, `id_pedido_vazio` | chaves obrigatórias |
| duplicidade | mantém a 1ª ocorrência de cada `id_pedido` |

**Invariante verificada em toda execução:**
`linhas lidas = carregadas + rejeitadas + duplicadas`.

## Resultado de referência (seed 42, 5.000 linhas)

| Métrica | Valor |
|---|---|
| Linhas lidas | 5.100 |
| Duplicados removidos | 100 |
| Rejeitados | 259 |
| Carregados | 4.741 (92,96 %) |
| Tempo | ~0,3 s |

## Decisões de projeto

- **Idempotência:** o esquema é recriado e carregado numa transação única; rodar
  duas vezes gera exatamente o mesmo resultado (coberto por teste).
- **Determinismo:** mesma `seed` → mesmos dados; facilita testes e comparações.
- **Rejeitar, não corrigir:** registros inválidos vão para `rejeitados.csv` com o
  motivo, para investigação na origem.
- **Evolução natural:** trocar SQLite por um banco corporativo e o gerador por
  uma extração real exige mudar apenas `extrair` e `carregar`.

## Sobre os dados

Os dados são **fictícios**, gerados por script (com semente fixa) para estudo; não vêm de nenhuma empresa.

## Autora

Vivian Ribeiro · [GitHub](https://github.com/ribeirovivi)
