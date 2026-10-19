"""Escritor mínimo de planilhas .xlsx (Excel) usando só a biblioteca padrão.

    escrever_xlsx("saida.xlsx", {"Vendas": (["id", "valor"], [["A1", 10.5], ["A2", 7]])})

Cada aba recebe: cabeçalho em negrito, linha de cabeçalho congelada, filtro
automático e largura de coluna ajustada. Números são gravados como número;
todo o resto como texto.
"""
import re
import zipfile
from xml.sax.saxutils import escape

_INVALIDOS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _letra(n):
    """0 -> A, 25 -> Z, 26 -> AA"""
    s, n = "", n + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _celula(ref, valor, cabecalho=False):
    estilo = ' s="1"' if cabecalho else ""
    if valor is None or valor == "":
        return f'<c r="{ref}"{estilo}/>'
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f'<c r="{ref}"{estilo}><v>{valor}</v></c>'
    texto = escape(_INVALIDOS.sub("", str(valor)))
    return f'<c r="{ref}"{estilo} t="inlineStr"><is><t xml:space="preserve">{texto}</t></is></c>'


def _nome_aba(nome, usados):
    limpo = re.sub(r"[\[\]:*?/\\]", " ", str(nome)).strip()[:31] or "Planilha"
    base, i = limpo, 2
    while limpo.lower() in usados:
        limpo = f"{base[:28]}_{i}"
        i += 1
    usados.add(limpo.lower())
    return limpo


def _aba_xml(colunas, linhas):
    larguras = [min(max(len(str(c)) + 3, 10), 60) for c in colunas]
    for linha in linhas[:200]:
        for i, v in enumerate(linha[: len(colunas)]):
            larguras[i] = min(max(larguras[i], len(str(v)) + 2), 60)
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>'
                   for i, w in enumerate(larguras))
    corpo = ['<row r="1">' + "".join(_celula(f"{_letra(i)}1", c, True)
                                     for i, c in enumerate(colunas)) + "</row>"]
    for n, linha in enumerate(linhas, start=2):
        corpo.append(f'<row r="{n}">' + "".join(
            _celula(f"{_letra(i)}{n}", v) for i, v in enumerate(linha)) + "</row>")
    ultima = f"{_letra(max(len(colunas) - 1, 0))}{len(linhas) + 1}"
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
            'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            f"<cols>{cols}</cols><sheetData>{''.join(corpo)}</sheetData>"
            f'<autoFilter ref="A1:{ultima}"/></worksheet>')


_ESTILOS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
            '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>'
            '<fills count="3"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
            '<fill><patternFill patternType="solid"><fgColor rgb="FF12306B"/>'
            '<bgColor indexed="64"/></patternFill></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
            '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
            '</styleSheet>')


def escrever_xlsx(caminho, abas):
    """abas: dict {nome: (lista_de_colunas, lista_de_linhas)}. Retorna o caminho."""
    usados, nomes, xmls = set(), [], []
    for nome, (colunas, linhas) in abas.items():
        nomes.append(_nome_aba(nome, usados))
        xmls.append(_aba_xml(list(colunas), [list(l) for l in linhas]))
    n = len(xmls)
    tipos = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
             '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
             + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                       for i in range(1, n + 1)) + "</Types>")
    raiz = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>")
    livro = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
             'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
             + "".join(f'<sheet name="{escape(nm, {chr(34): "&quot;"})}" sheetId="{i}" r:id="rId{i}"/>'
                       for i, nm in enumerate(nomes, start=1)) + "</sheets></workbook>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                      for i in range(1, n + 1))
            + f'<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            "</Relationships>")
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipos)
        z.writestr("_rels/.rels", raiz)
        z.writestr("xl/workbook.xml", livro)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/styles.xml", _ESTILOS)
        for i, xml in enumerate(xmls, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", xml)
    return caminho
