"""Gera dados brutos de vendas, propositalmente "sujos" (duplicatas, nulos, datas
inválidas, valores impossíveis), para exercitar as regras de qualidade do pipeline.

Tudo é determinístico: a mesma semente (seed) gera sempre os mesmos arquivos.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

PRODUTOS = [
    ("P001", "Notebook 14", "Informática", 3499.90),
    ("P002", "Monitor 24", "Informática", 899.00),
    ("P003", "Teclado Mecânico", "Periféricos", 289.90),
    ("P004", "Mouse sem fio", "Periféricos", 119.90),
    ("P005", "Headset", "Periféricos", 249.00),
    ("P006", "Cadeira Ergonômica", "Escritório", 1290.00),
    ("P007", "Mesa Ajustável", "Escritório", 1890.00),
    ("P008", "Webcam HD", "Informática", 199.90),
]
UFS = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "PE", "CE"]
CANAIS = ["Loja online", "Aplicativo", "Televendas", "Parceiros"]
SEGMENTOS = ["Varejo", "Corporativo", "Governo"]
CAMPOS = ["id_pedido", "data_pedido", "id_cliente", "nome_cliente", "segmento",
          "uf", "id_produto", "quantidade", "preco_unitario", "desconto_pct", "canal"]


def gerar(pasta, linhas=5000, seed=42):
    """Escreve vendas_brutas.csv e produtos.csv em `pasta`. Retorna os caminhos."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(seed)

    clientes = [(f"C{n:04d}", f"Cliente {n:04d}", rnd.choice(SEGMENTOS), rnd.choice(UFS))
                for n in range(1, 401)]
    inicio = date(2025, 1, 1)

    registros = []
    for i in range(1, linhas + 1):
        cid, nome, seg, uf = rnd.choice(clientes)
        pid, _, _, preco = rnd.choice(PRODUTOS)
        dia = inicio + timedelta(days=rnd.randrange(0, 365))
        # dois formatos de data de propósito (ISO e brasileiro)
        data_txt = dia.isoformat() if rnd.random() < 0.8 else dia.strftime("%d/%m/%Y")
        registros.append({
            "id_pedido": f"PED{i:06d}", "data_pedido": data_txt, "id_cliente": cid,
            "nome_cliente": nome, "segmento": seg, "uf": uf, "id_produto": pid,
            "quantidade": str(rnd.randint(1, 5)),
            "preco_unitario": f"{preco:.2f}",
            "desconto_pct": str(rnd.choice([0, 0, 5, 10, 15])),
            "canal": rnd.choice(CANAIS),
        })

    n = len(registros)
    # problemas injetados (percentuais sobre o total)
    for r in rnd.sample(registros, int(n * 0.015)):
        r["quantidade"] = str(rnd.choice([0, -1]))
    for r in rnd.sample(registros, int(n * 0.010)):
        r["data_pedido"] = "31/02/2025"          # data inexistente
    for r in rnd.sample(registros, int(n * 0.010)):
        r["uf"] = ""                              # campo obrigatório vazio
    for r in rnd.sample(registros, int(n * 0.008)):
        r["preco_unitario"] = "-10.00"            # preço impossível
    for r in rnd.sample(registros, int(n * 0.010)):
        r["desconto_pct"] = "150"                 # desconto acima de 100%
    duplicados = [dict(r) for r in rnd.sample(registros, int(n * 0.02))]
    registros += duplicados                       # mesmas linhas repetidas
    rnd.shuffle(registros)

    caminho_vendas = pasta / "vendas_brutas.csv"
    with caminho_vendas.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(registros)

    caminho_produtos = pasta / "produtos.csv"
    with caminho_produtos.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id_produto", "nome_produto", "categoria", "preco_lista"])
        w.writerows(PRODUTOS)

    return caminho_vendas, caminho_produtos
