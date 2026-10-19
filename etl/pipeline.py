"""Etapas do pipeline: extrair -> validar/limpar -> transformar -> carregar (DW estrela).

Somente biblioteca padrão do Python (csv, sqlite3, datetime).
"""
import csv
import sqlite3
from collections import Counter
from datetime import date, datetime
from pathlib import Path

DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

SCHEMA = """
DROP TABLE IF EXISTS fato_vendas;
DROP TABLE IF EXISTS dim_cliente;
DROP TABLE IF EXISTS dim_produto;
DROP TABLE IF EXISTS dim_tempo;

CREATE TABLE dim_cliente (
    id_cliente TEXT PRIMARY KEY, nome TEXT NOT NULL, segmento TEXT NOT NULL, uf TEXT NOT NULL);
CREATE TABLE dim_produto (
    id_produto TEXT PRIMARY KEY, nome TEXT NOT NULL, categoria TEXT NOT NULL, preco_lista REAL NOT NULL);
CREATE TABLE dim_tempo (
    id_data INTEGER PRIMARY KEY, data TEXT NOT NULL, ano INTEGER, mes INTEGER,
    trimestre INTEGER, dia_semana TEXT);
CREATE TABLE fato_vendas (
    id_pedido TEXT PRIMARY KEY,
    id_data INTEGER NOT NULL REFERENCES dim_tempo(id_data),
    id_cliente TEXT NOT NULL REFERENCES dim_cliente(id_cliente),
    id_produto TEXT NOT NULL REFERENCES dim_produto(id_produto),
    canal TEXT NOT NULL,
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    preco_unitario REAL NOT NULL CHECK (preco_unitario > 0),
    desconto_pct REAL NOT NULL CHECK (desconto_pct BETWEEN 0 AND 100),
    valor_bruto REAL NOT NULL,
    valor_desconto REAL NOT NULL,
    valor_liquido REAL NOT NULL);
CREATE INDEX ix_fato_data ON fato_vendas(id_data);
CREATE INDEX ix_fato_produto ON fato_vendas(id_produto);
"""


# ---------------------------------------------------------------- extrair
def extrair(caminho):
    """Lê o CSV bruto como lista de dicionários (tudo texto)."""
    with Path(caminho).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def extrair_produtos(caminho):
    with Path(caminho).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------- validar
def parse_data(texto):
    """Aceita AAAA-MM-DD e DD/MM/AAAA. Retorna date ou None se inválida."""
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime((texto or "").strip(), formato).date()
        except ValueError:
            continue
    return None


def validar(registro, produtos_validos):
    """Devolve a lista de regras violadas (vazia = registro válido)."""
    motivos = []
    if not (registro.get("id_pedido") or "").strip():
        motivos.append("id_pedido_vazio")
    if parse_data(registro.get("data_pedido")) is None:
        motivos.append("data_invalida")
    if not (registro.get("id_cliente") or "").strip():
        motivos.append("cliente_vazio")
    if not (registro.get("uf") or "").strip():
        motivos.append("uf_vazia")
    if registro.get("id_produto") not in produtos_validos:
        motivos.append("produto_desconhecido")
    try:
        if int(registro.get("quantidade", "")) <= 0:
            motivos.append("quantidade_invalida")
    except ValueError:
        motivos.append("quantidade_invalida")
    try:
        if float(registro.get("preco_unitario", "")) <= 0:
            motivos.append("preco_invalido")
    except ValueError:
        motivos.append("preco_invalido")
    try:
        if not 0 <= float(registro.get("desconto_pct", "")) <= 100:
            motivos.append("desconto_invalido")
    except ValueError:
        motivos.append("desconto_invalido")
    return motivos


def limpar(registros, produtos_validos):
    """Remove duplicatas (mantém a 1ª ocorrência) e separa rejeitados.

    Retorna (validos, rejeitados, qtd_duplicados, contagem_por_regra).
    Invariante: len(registros) == len(validos) + len(rejeitados) + qtd_duplicados.
    """
    vistos, validos, rejeitados = set(), [], []
    duplicados = 0
    por_regra = Counter()
    for r in registros:
        chave = r.get("id_pedido")
        if chave in vistos:
            duplicados += 1
            continue
        vistos.add(chave)
        motivos = validar(r, produtos_validos)
        if motivos:
            rejeitados.append({**r, "motivos": "|".join(motivos)})
            por_regra.update(motivos)
        else:
            validos.append(r)
    return validos, rejeitados, duplicados, dict(por_regra)


# ------------------------------------------------------------ transformar
def transformar(validos, produtos):
    """Converte tipos, calcula valores e monta as tabelas do modelo estrela."""
    dim_cliente, dim_tempo, fatos = {}, {}, []
    for r in validos:
        dia = parse_data(r["data_pedido"])
        id_data = int(dia.strftime("%Y%m%d"))
        qtd = int(r["quantidade"])
        preco = float(r["preco_unitario"])
        desc = float(r["desconto_pct"])
        bruto = round(qtd * preco, 2)
        valor_desc = round(bruto * desc / 100, 2)
        dim_cliente.setdefault(r["id_cliente"], (r["id_cliente"], r["nome_cliente"].strip(),
                                                 r["segmento"].strip(), r["uf"].strip().upper()))
        dim_tempo.setdefault(id_data, (id_data, dia.isoformat(), dia.year, dia.month,
                                       (dia.month - 1) // 3 + 1, DIAS_SEMANA[dia.weekday()]))
        fatos.append((r["id_pedido"], id_data, r["id_cliente"], r["id_produto"], r["canal"],
                      qtd, preco, desc, bruto, valor_desc, round(bruto - valor_desc, 2)))
    dim_produto = [(p["id_produto"], p["nome_produto"], p["categoria"], float(p["preco_lista"]))
                   for p in produtos]
    return {"dim_cliente": list(dim_cliente.values()), "dim_produto": dim_produto,
            "dim_tempo": sorted(dim_tempo.values()), "fato_vendas": fatos}


# --------------------------------------------------------------- carregar
def carregar(caminho_db, tabelas):
    """Recria o esquema e carrega as tabelas numa transação (idempotente)."""
    con = sqlite3.connect(caminho_db)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        with con:  # commit/rollback automático
            con.executescript(SCHEMA)
            con.executemany("INSERT INTO dim_cliente VALUES (?,?,?,?)", tabelas["dim_cliente"])
            con.executemany("INSERT INTO dim_produto VALUES (?,?,?,?)", tabelas["dim_produto"])
            con.executemany("INSERT INTO dim_tempo VALUES (?,?,?,?,?,?)", tabelas["dim_tempo"])
            con.executemany("INSERT INTO fato_vendas VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            tabelas["fato_vendas"])
        return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tabelas}
    finally:
        con.close()
