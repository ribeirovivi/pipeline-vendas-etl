import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etl import gerar_dados, pipeline  # noqa: E402

PRODUTOS_OK = {"P001", "P002"}
BASE = {"id_pedido": "PED1", "data_pedido": "2025-03-10", "id_cliente": "C0001",
        "nome_cliente": "Cliente 1", "segmento": "Varejo", "uf": "SP", "id_produto": "P001",
        "quantidade": "2", "preco_unitario": "100.00", "desconto_pct": "10", "canal": "Aplicativo"}


class TestRegras(unittest.TestCase):
    def test_parse_data_aceita_dois_formatos(self):
        self.assertEqual(pipeline.parse_data("2025-03-10"), date(2025, 3, 10))
        self.assertEqual(pipeline.parse_data("10/03/2025"), date(2025, 3, 10))

    def test_parse_data_rejeita_data_inexistente(self):
        self.assertIsNone(pipeline.parse_data("31/02/2025"))

    def test_registro_valido(self):
        self.assertEqual(pipeline.validar(BASE, PRODUTOS_OK), [])

    def test_cada_regra_dispara(self):
        casos = {"quantidade": ("0", "quantidade_invalida"), "uf": ("", "uf_vazia"),
                 "preco_unitario": ("-1", "preco_invalido"),
                 "desconto_pct": ("150", "desconto_invalido"),
                 "id_produto": ("PX", "produto_desconhecido"),
                 "data_pedido": ("31/02/2025", "data_invalida")}
        for campo, (valor, regra) in casos.items():
            with self.subTest(regra=regra):
                self.assertIn(regra, pipeline.validar({**BASE, campo: valor}, PRODUTOS_OK))


class TestLimpezaETransformacao(unittest.TestCase):
    def test_deduplicacao_e_invariante(self):
        regs = [BASE, dict(BASE), {**BASE, "id_pedido": "PED2", "quantidade": "0"}]
        validos, rej, dup, _ = pipeline.limpar(regs, PRODUTOS_OK)
        self.assertEqual((len(validos), len(rej), dup), (1, 1, 1))
        self.assertEqual(len(regs), len(validos) + len(rej) + dup)

    def test_calculo_de_valores(self):
        prods = [{"id_produto": "P001", "nome_produto": "X", "categoria": "Y", "preco_lista": "100"}]
        fato = pipeline.transformar([BASE], prods)["fato_vendas"][0]
        self.assertEqual((fato[8], fato[9], fato[10]), (200.0, 20.0, 180.0))


class TestFimAFim(unittest.TestCase):
    def test_pipeline_completo_e_idempotente(self):
        with tempfile.TemporaryDirectory() as tmp:
            v, p = gerar_dados.gerar(tmp, linhas=800, seed=1)
            regs, prods = pipeline.extrair(v), pipeline.extrair_produtos(p)
            validos, rej, dup, _ = pipeline.limpar(regs, {x["id_produto"] for x in prods})
            self.assertGreater(dup, 0)
            self.assertGreater(len(rej), 0)
            tabelas = pipeline.transformar(validos, prods)
            db = Path(tmp) / "dw.sqlite"
            c1 = pipeline.carregar(db, tabelas)
            c2 = pipeline.carregar(db, tabelas)          # 2ª carga = mesmo resultado
            self.assertEqual(c1, c2)
            self.assertEqual(c1["fato_vendas"], len(validos))
            con = sqlite3.connect(db)
            órfãos = con.execute("""SELECT COUNT(*) FROM fato_vendas f
                LEFT JOIN dim_cliente c USING(id_cliente) WHERE c.id_cliente IS NULL""").fetchone()[0]
            con.close()
            self.assertEqual(órfãos, 0)

    def test_geracao_deterministica(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            va, _ = gerar_dados.gerar(a, 300, seed=9)
            vb, _ = gerar_dados.gerar(b, 300, seed=9)
            self.assertEqual(va.read_text(encoding="utf-8"), vb.read_text(encoding="utf-8"))


class TestEntradaPropriaEExcel(unittest.TestCase):
    def test_cli_com_csv_proprio_gera_xlsx_valido(self):
        import io
        import json
        import zipfile
        from contextlib import redirect_stdout
        import run_pipeline
        with tempfile.TemporaryDirectory() as tmp:
            v, _ = gerar_dados.gerar(Path(tmp) / "meus_dados", linhas=400, seed=3)
            saida = Path(tmp) / "saida"
            with redirect_stdout(io.StringIO()):
                codigo = run_pipeline.main(["--entrada", str(v), "--saida", str(saida)])
            self.assertEqual(codigo, 0)
            q = json.loads((saida / "qualidade.json").read_text(encoding="utf-8"))
            self.assertEqual(q["linhas_lidas"], q["carregados"] + q["rejeitados"] + q["duplicados_removidos"])
            with zipfile.ZipFile(saida / "vendas_dw.xlsx") as z:
                self.assertIsNone(z.testzip())
                self.assertIn("xl/worksheets/sheet1.xml", z.namelist())

    def test_entrada_inexistente_retorna_erro(self):
        import io
        from contextlib import redirect_stdout
        import run_pipeline
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            self.assertEqual(run_pipeline.main(["--entrada", str(Path(tmp) / "nao_existe.csv"),
                                                "--saida", str(Path(tmp) / "s")]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
