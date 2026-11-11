from __future__ import annotations

from pathlib import Path

from ..errors import ConversionFailedError, DependencyError
from ..registry import converter
from ..textio import decode_text, split_paragraphs, write_text


def _require_docx():
    try:
        import docx
    except ImportError as exc:
        raise DependencyError(
            "Brak biblioteki python-docx.",
            "Zainstaluj zależności: pip install -r requirements.txt.",
        ) from exc
    return docx


def _require_odf():
    try:
        from odf import text as odf_text
        from odf.opendocument import OpenDocumentText, load
        from odf.namespaces import TABLENS, TEXTNS
        from odf.table import TableCell, TableRow
    except ImportError as exc:
        raise DependencyError(
            "Brak biblioteki odfpy.",
            "Zainstaluj zależności: pip install -r requirements.txt.",
        ) from exc
    return {
        "OpenDocumentText": OpenDocumentText,
        "load": load,
        "P": odf_text.P,
        "LineBreak": odf_text.LineBreak,
        "TEXTNS": TEXTNS,
        "TABLENS": TABLENS,
        "TableCell": TableCell,
        "TableRow": TableRow,
    }


@converter(".txt", ".docx")
def txt_to_docx(source: Path, target: Path) -> Path:
    docx = _require_docx()
    text = decode_text(source)
    document = docx.Document()

    for lines in split_paragraphs(text):
        paragraph = document.add_paragraph()
        for index, line in enumerate(lines):
            run = paragraph.add_run(line)
            if index < len(lines) - 1:
                run.add_break()

    document.save(str(target))
    return target


@converter(".txt", ".odt")
def txt_to_odt(source: Path, target: Path) -> Path:
    odf = _require_odf()
    text = decode_text(source)
    document = odf["OpenDocumentText"]()

    for lines in split_paragraphs(text):
        paragraph = odf["P"]()
        for index, line in enumerate(lines):
            paragraph.addText(line)
            if index < len(lines) - 1:
                paragraph.addElement(odf["LineBreak"]())
        document.text.addElement(paragraph)

    document.save(str(target))
    return target


@converter(".docx", ".txt")
def docx_to_txt(source: Path, target: Path) -> Path:
    docx = _require_docx()
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = docx.Document(str(source))
    except Exception as exc:
        raise ConversionFailedError(
            f"Nie można otworzyć pliku DOCX: {source.name}.",
            "Plik może być uszkodzony lub mieć inne rozszerzenie niż zawartość.",
        ) from exc

    blocks: list[str] = []
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            blocks.append(Paragraph(child, document).text)
        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            rows = []
            for row in table.rows:
                cells = [cell.text.replace("\n", " ").strip() for cell in row.cells]
                rows.append("\t".join(cells))
            blocks.append("\n".join(rows))

    content = "\n\n".join(blocks).strip("\n")
    return write_text(target, f"{content}\n" if content else "")


def _odt_text(element, text_ns: str) -> str:
    chunks: list[str] = []
    for node in element.childNodes:
        if node.nodeType == 3:
            chunks.append(node.data)
            continue
        qname = getattr(node, "qname", None)
        if qname == (text_ns, "line-break"):
            chunks.append("\n")
        elif qname == (text_ns, "tab"):
            chunks.append("\t")
        elif qname == (text_ns, "s"):
            chunks.append(" ")
        elif getattr(node, "childNodes", None):
            chunks.append(_odt_text(node, text_ns))
    return "".join(chunks)


def _odt_blocks(container, text_ns: str, table_ns: str, row_type, cell_type) -> list[str]:
    parts: list[str] = []
    for child in container.childNodes:
        qname = getattr(child, "qname", None)
        if qname in ((text_ns, "p"), (text_ns, "h")):
            parts.append(_odt_text(child, text_ns))
        elif qname == (table_ns, "table"):
            rows = []
            for row in child.getElementsByType(row_type):
                cells = [
                    _odt_text(cell, text_ns).replace("\n", " ").strip()
                    for cell in row.getElementsByType(cell_type)
                ]
                rows.append("\t".join(cells))
            parts.append("\n".join(rows))
        elif qname in ((text_ns, "list"), (text_ns, "section")):
            parts.extend(_odt_blocks(child, text_ns, table_ns, row_type, cell_type))
    return parts


@converter(".odt", ".txt")
def odt_to_txt(source: Path, target: Path) -> Path:
    odf = _require_odf()

    try:
        document = odf["load"](str(source))
        blocks = _odt_blocks(
            document.text,
            odf["TEXTNS"],
            odf["TABLENS"],
            odf["TableRow"],
            odf["TableCell"],
        )
    except Exception as exc:
        raise ConversionFailedError(
            f"Nie można otworzyć pliku ODT: {source.name}.",
            "Plik może być uszkodzony lub mieć inne rozszerzenie niż zawartość.",
        ) from exc

    content = "\n\n".join(blocks).strip("\n")
    return write_text(target, f"{content}\n" if content else "")
