"""Page-break fix-ups for QTextDocument PDF reports.

QTextDocument paginates like a browser printing with no CSS paging rules:
a heading can end a page while what it introduces starts the next one, a
table row splits across a page boundary line by line, and a two-line
paragraph can leave one line behind. Qt has no keep-with-next or
keep-together, but it does honour PageBreak_AlwaysBefore on any block,
including the first block of a table cell (which moves that whole row).

keep_together() lays the document out at its page size, finds the first
such break, forces a page break before the offending heading / row /
paragraph, and repeats until nothing is left to fix. Each fix only moves
content further down, so earlier fixes stay valid.

Call it after setHtml(), embed_figures() and setPageSize(), right before
printing.
"""
from __future__ import annotations

from PyQt6.QtGui import QTextBlockFormat, QTextCursor, QTextDocument, QTextFormat

from core.vector_figures import _relayout

# Rows / paragraphs taller than this share of a page are allowed to split:
# moving them would leave most of a page blank and still not fit.
_MAX_KEEP_SHARE = 0.5
# A paragraph of at most this many lines is never split across pages.
_SHORT_PARAGRAPH_LINES = 4

_ALWAYS_BEFORE = QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore


def _breaks_before(block) -> bool:
    return bool(block.blockFormat().pageBreakPolicy() & _ALWAYS_BEFORE)


def _first_violation(doc: QTextDocument, page_h: float) -> list[int] | None:
    """Positions of the blocks to put a page break before, for the topmost
    bad break in the document; None when there is none."""
    lay = doc.documentLayout()

    def page(y: float) -> int:
        return int(y // page_h)

    found: list[tuple[float, list[int]]] = []  # (y, block positions)
    rows: dict[tuple[int, int], list] = {}      # (table start, row) -> [top, bottom, table, row]
    b = doc.begin()
    while b.isValid():
        rect = lay.blockBoundingRect(b)
        cur = QTextCursor(b)
        table = cur.currentTable()
        if table is not None:
            cell = table.cellAt(cur)
            if cell.row() >= table.format().headerRowCount():
                key = (table.firstPosition(), cell.row())
                entry = rows.setdefault(key, [rect.top(), rect.bottom(), table, cell.row()])
                entry[0] = min(entry[0], rect.top())
                entry[1] = max(entry[1], rect.bottom())
        elif b.blockFormat().headingLevel() > 0:
            # Keep with the first line of the next non-heading block.
            nxt = b.next()
            while nxt.isValid() and (nxt.blockFormat().headingLevel() > 0 or not nxt.text().strip()
                                     and nxt.length() <= 1):
                nxt = nxt.next()
            if nxt.isValid():
                nrect = lay.blockBoundingRect(nxt)
                line = nxt.layout().lineAt(0)
                first_bottom = nrect.top() + (line.rect().bottom() if line.isValid() else nrect.height())
                if page(rect.top()) != page(first_bottom - 1) and not _breaks_before(b) \
                        and rect.height() < page_h * _MAX_KEEP_SHARE:
                    found.append((rect.top(), [b.position()]))
        else:
            n_lines = b.layout().lineCount()
            if 1 < n_lines <= _SHORT_PARAGRAPH_LINES and page(rect.top()) != page(rect.bottom() - 1) \
                    and not _breaks_before(b):
                found.append((rect.top(), [b.position()]))
        b = b.next()

    for top, bottom, table, row in rows.values():
        if page(top) == page(bottom - 1) or bottom - top > page_h * _MAX_KEEP_SHARE:
            continue
        cells = [table.cellAt(row, c) for c in range(table.columns())]
        positions = sorted({c.firstCursorPosition().position() for c in cells if c.isValid()})
        first = doc.findBlock(positions[0]) if positions else None
        if first is not None and not _breaks_before(first):
            found.append((top, positions))
    if not found:
        return None
    return min(found, key=lambda f: f[0])[1]


def keep_together(doc: QTextDocument, max_passes: int = 80) -> int:
    """Fix bad page breaks in place (see the module docstring); returns how
    many page breaks were inserted."""
    page_h = doc.pageSize().height()
    if page_h <= 0:
        return 0
    fmt = QTextBlockFormat()
    fmt.setPageBreakPolicy(_ALWAYS_BEFORE)
    inserted = 0
    _relayout(doc)
    for _ in range(max_passes):
        positions = _first_violation(doc, page_h)
        if not positions:
            break
        for pos in positions:
            cur = QTextCursor(doc)
            cur.setPosition(pos)
            cur.mergeBlockFormat(fmt)
        _relayout(doc)
        inserted += 1
    return inserted
