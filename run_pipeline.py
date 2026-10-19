#!/usr/bin/env python3
"""Executa o pipeline completo: dados brutos -> ETL -> DW SQLite -> relatórios.

Uso:
    python run_pipeline.py                                  # gera 5.000 linhas (seed 42)
    python run_pipeline.py --linhas 20000 --seed 7 --saida resultado
    python run_pipeline.py --entrada dados/vendas_brutas.csv   # usa SEU CSV
"""
import argparse
import csv
import json
import sqlite3
import sys
import time
from pathlib import Path

from etl import gerar_dados, pipeline
from etl.xlsx_simples import escrever_xlsx

CONSULTAS = {
    "Receita líquida por mês": """
        SELECT t.ano || '-' || printf('%02d', t.mes) AS mes,
               COUNT(*) AS pedidos, ROUND(SUM(f.valor_liquido), 2) AS receita
        FROM fato_vendas f JOIN dim_tempo t USING (id_data)
        GROUP BY t.ano, t.mes ORDER BY t.ano, t.mes""",
    "Top 5 produtos por receita": """
        SELECT p.nome, p.categoria, SUM(f.quantidade) AS unidades,
               ROUND(SUM(f.valor_liquido), 2) AS receita
        FROM fato_vendas f JOIN dim_produto p USING (id_produto)
        GROUP BY p.id_produto ORDER BY receita DESC LIMIT 5""",
    "Receita e ticket médio por canal": """
        SELECT canal, COUNT(*) AS pedidos, ROUND(SUM(valor_liquido), 2) AS receita,
               ROUND(AVG(valor_liquido), 2) AS ticket_medio
        FROM fato_vendas GROUP BY canal ORDER BY receita DESC""",
    "Receita por segmento de cliente": """
        SELECT c.segmento, COUNT(DISTINCT c.id_cliente) AS clientes,
               ROUND(SUM(f.valor_liquido), 2) AS receita
        FROM fato_vendas f JOIN dim_cliente c USING (id_cliente)
        GROUP BY c.segmento ORDER BY receita DESC""",
}
CAMPOS_BRUTOS = gerar_dados.CAMPOS


def tabela_md(colunas, linhas):
    cab = "| " + " | ".join(colunas) + " |\n|" + "---|" * len(colunas) + "\n"
    return cab + "\n".join("| " + " | ".join(str(v) for v in l) + " |" for l in linhas) + "\n"


def tabela_sqlite(con, nome):
    cur = con.execute(f"SELECT * FROM {nome}")
    return [d[0] for d in cur.description], cur.fetchall()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--entrada", help="CSV bruto próprio (UTF-8). Se omitido, gera dados de exemplo.")
    ap.add_argument("--produtos", help="CSV de produtos (padrão: produtos.csv ao lado da entrada)")
    ap.add_argument("--linhas", type=int, default=5000, help="linhas geradas (padrão 5000)")
    ap.add_argument("--seed", type=int, default=42, help="semente aleatória (padrão 42)")
    ap.add_argument("--saida", default="saida", help="pasta de saída (padrão: saida)")
    args = ap.parse_args(argv)

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    # 1) fonte: CSV do usuário ou dados simulados
    if args.entrada:
        csv_vendas = Path(args.entrada)
        csv_produtos = Path(args.produtos) if args.produtos else csv_vendas.with_name("produtos.csv")
        if not csv_vendas.exists() or not csv_produtos.exists():
            print(f"Arquivo não encontrado: {csv_vendas if not csv_vendas.exists() else csv_produtos}")
            return 1
    else:
        csv_vendas, csv_produtos = gerar_dados.gerar(saida / "bruto", args.linhas, args.seed)

    # 2) extrair -> validar/limpar -> transformar -> carregar
    registros = pipeline.extrair(csv_vendas)
    produtos = pipeline.extrair_produtos(csv_produtos)
    validos, rejeitados, duplicados, por_regra = pipeline.limpar(
        registros, {p["id_produto"] for p in produtos})
    tabelas = pipeline.transformar(validos, produtos)
    contagens = pipeline.carregar(saida / "vendas_dw.sqlite", tabelas)

    # 3) reconciliação: nada pode "sumir" no caminho
    lidos = len(registros)
    carregados = contagens["fato_vendas"]
    assert lidos == carregados + len(rejeitados) + duplicados, "reconciliação falhou"

    # 4) rejeitados para investigação
    if rejeitados:
        with (saida / "rejeitados.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rejeitados[0].keys()))
            w.writeheader()
            w.writerows(rejeitados)

    # 5) relatório de qualidade
    qualidade = {
        "linhas_lidas": lidos, "duplicados_removidos": duplicados,
        "rejeitados": len(rejeitados), "carregados": carregados,
        "taxa_aprovacao_pct": round(100 * carregados / lidos, 2) if lidos else 0.0,
        "violacoes_por_regra": dict(sorted(por_regra.items(), key=lambda kv: -kv[1])),
        "tabelas_carregadas": contagens,
        "duracao_segundos": round(time.perf_counter() - t0, 2),
    }
    (saida / "qualidade.json").write_text(
        json.dumps(qualidade, ensure_ascii=False, indent=2), encoding="utf-8")

    # 6) consultas analíticas (markdown + Excel)
    con = sqlite3.connect(saida / "vendas_dw.sqlite")
    partes = ["# Relatório do pipeline de vendas\n",
              "## Qualidade dos dados\n",
              tabela_md(["Métrica", "Valor"], [
                  ["Linhas lidas", lidos], ["Duplicados removidos", duplicados],
                  ["Rejeitados (regras)", len(rejeitados)], ["Carregados no DW", carregados],
                  ["Taxa de aprovação", f"{qualidade['taxa_aprovacao_pct']}%"]]),
              "\n### Violações por regra\n",
              tabela_md(["Regra", "Ocorrências"], list(qualidade["violacoes_por_regra"].items()))]
    abas = {"Qualidade": (["Métrica", "Valor"], [
        ["Linhas lidas", lidos], ["Duplicados removidos", duplicados],
        ["Rejeitados (regras)", len(rejeitados)], ["Carregados no DW", carregados],
        ["Taxa de aprovação (%)", qualidade["taxa_aprovacao_pct"]]]
        + [[f"Violação: {r}", n] for r, n in qualidade["violacoes_por_regra"].items()])}
    for titulo, sql in CONSULTAS.items():
        cur = con.execute(sql)
        colunas, linhas = [d[0] for d in cur.description], cur.fetchall()
        partes += [f"\n## {titulo}\n", tabela_md(colunas, linhas)]
        abas[titulo] = (colunas, linhas)
    for nome in ("fato_vendas", "dim_cliente", "dim_produto", "dim_tempo"):
        abas[nome] = tabela_sqlite(con, nome)
    con.close()
    if rejeitados:
        cols = list(rejeitados[0].keys())
        abas["rejeitados"] = (cols, [[r[c] for c in cols] for r in rejeitados])
    escrever_xlsx(saida / "vendas_dw.xlsx", abas)

    relatorio = "\n".join(partes)
    (saida / "relatorio.md").write_text(relatorio, encoding="utf-8")

    print(relatorio)
    print(f"\nOK em {qualidade['duracao_segundos']}s. Arquivos em: {saida.resolve()}")
    print("  vendas_dw.sqlite (banco) | vendas_dw.xlsx (Excel) | relatorio.md | "
          "qualidade.json | rejeitados.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
