"""Page-break fix-ups for QTextDocument PDF reports.

QTextDocument paginates like a browser printing with no CSS paging rules:
a heading can end a page while what it introduces starts the next one, a
table splits across a page boundary between (or inside) its rows, a figure
caption lands on the page after its figure, and a two-line paragraph can
leave one line behind. Qt has no keep-with-next or keep-together, but it
honours PageBreak_AlwaysBefore on a block and on a table as a whole.

(Not on a table row: a break set on the first block of a cell is also
honoured, but with image cells or a repeated <thead> Qt then renders blank
pages holding only the table's borders or header. So a table that has to
move moves whole, and a table too tall for that splits as before.)

A vector figure that does not fit under the text above it and would leave a
third of a page blank is first scaled down to fill that gap (to no less than
70% of its size). Then keep_together() lays the document out at its page
size, finds the first
such break, forces a page break before the offending heading, paragraph,
table, or the figure whose "Figure N." caption would start or run onto the
next page, and repeats until nothing is left to fix. Each fix only moves
content further down, so earlier fixes stay valid.

Call it after setHtml(), embed_figures() and setPageSize(), right before
printing.
"""
from __future__ import annotations

import re

from PyQt6.QtGui import QTextBlockFormat, QTextCursor, QTextDocument, QTextFormat

from core.vector_figures import _HEIGHT_PROP, _OBJECT_TYPE, _WIDTH_PROP, _relayout

# Headings taller than this share of a page are allowed to end a page.
_MAX_KEEP_SHARE = 0.5
# A table up to this share of a page moves to the next page whole rather than
# splitting; a taller one would leave too much of a page blank.
_MAX_TABLE_SHARE = 0.6
# A paragraph of at most this many lines is never split across pages.
_SHORT_PARAGRAPH_LINES = 4
# Lines of the following paragraph a heading keeps on its page.
_HEADING_LINES = 3

_ALWAYS_BEFORE = QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore

# A figure caption ("Figure 3. ..."), kept on the page of the figure above it.
_CAPTION_RE = re.compile(r"^Figure \d+\.")
# The object replacement character an inline image / vector figure occupies.
_OBJECT_CHAR = "￼"


def _breaks_before(block) -> bool:
    return bool(block.blockFormat().pageBreakPolicy() & _ALWAYS_BEFORE)


def _blank(block) -> bool:
    return not block.text().strip() and block.length() <= 1


def _lead_in(block):
    """The heading (with any heading above it, and a short intro paragraph
    under it) that directly introduces `block`, or None. Whatever has to move
    to the next page takes its lead-in along: breaking before the table and
    then again before its orphaned heading left a page holding only the
    heading."""
    prev = block.previous()
    while prev.isValid() and _blank(prev):
        prev = prev.previous()
    if prev.isValid() and prev.blockFormat().headingLevel() == 0 \
            and QTextCursor(prev).currentTable() is None and _OBJECT_CHAR not in prev.text() \
            and prev.layout().lineCount() <= _SHORT_PARAGRAPH_LINES:
        intro = prev.previous()
        while intro.isValid() and _blank(intro):
            intro = intro.previous()
        prev = intro if intro.isValid() and intro.blockFormat().headingLevel() > 0 else None
    if prev is None or not prev.isValid() or prev.blockFormat().headingLevel() == 0:
        return None
    while prev.previous().isValid() and prev.previous().blockFormat().headingLevel() > 0:
        prev = prev.previous()
    return prev


def _heading_above(block):
    """The heading run directly above `block` (and that run's own lead-in),
    or None: a paragraph that must move takes the heading it sits under."""
    prev = block.previous()
    while prev.isValid() and _blank(prev):
        prev = prev.previous()
    if not prev.isValid() or prev.blockFormat().headingLevel() == 0:
        return None
    while prev.previous().isValid() and prev.previous().blockFormat().headingLevel() > 0:
        prev = prev.previous()
    return _lead_in(prev) or prev


def _first_violation(doc: QTextDocument, page_h: float) -> tuple[str, int] | None:
    """The fix for the topmost bad break in the document: ("block", position)
    to break before that block, or ("table", first position) to move that
    table to the next page; None when there is nothing to fix."""
    lay = doc.documentLayout()

    def page(y: float) -> int:
        return int(y // page_h)

    def first_line_bottom(block, lines: int = 1) -> float:
        """Bottom of the block's first `lines` lines (all of them if fewer)."""
        r = lay.blockBoundingRect(block)
        layout = block.layout()
        n = min(lines, layout.lineCount())
        line = layout.lineAt(n - 1) if n else layout.lineAt(0)
        return r.top() + (line.rect().bottom() if line.isValid() else r.height())

    found: list[tuple[float, tuple[str, int]]] = []
    tables: dict[int, list] = {}      # first position -> [top, bottom, table, {row: [top, bottom]}]
    b = doc.begin()
    while b.isValid():
        rect = lay.blockBoundingRect(b)
        table = QTextCursor(b).currentTable()
        if table is not None:
            entry = tables.setdefault(table.firstPosition(), [rect.top(), rect.bottom(), table, {}])
            entry[0] = min(entry[0], rect.top())
            entry[1] = max(entry[1], rect.bottom())
            row = entry[3].setdefault(table.cellAt(b.position()).row(), [rect.top(), rect.bottom()])
            row[0] = min(row[0], rect.top())
            row[1] = max(row[1], rect.bottom())
        elif b.blockFormat().headingLevel() > 0:
            # Keep with the first line of the next non-heading block...
            nxt = b.next()
            while nxt.isValid() and (nxt.blockFormat().headingLevel() > 0 or _blank(nxt)):
                nxt = nxt.next()
            # ...and past a short intro paragraph ("Step 5: ..." and its
            # one-line description), or heading and intro end a page above
            # their table.
            if nxt.isValid() and QTextCursor(nxt).currentTable() is None \
                    and _OBJECT_CHAR not in nxt.text() and nxt.layout().lineCount() <= _SHORT_PARAGRAPH_LINES:
                after = nxt.next()
                while after.isValid() and _blank(after):
                    after = after.next()
                if after.isValid() and after.blockFormat().headingLevel() == 0:
                    nxt = after
            # Text keeps HEADING_LINES lines under its heading: one line left
            # behind ("Scale-down" + its first line at a page bottom) reads as
            # an orphaned heading too.
            keep = _HEADING_LINES if QTextCursor(nxt).currentTable() is None and nxt.isValid() \
                and _OBJECT_CHAR not in nxt.text() else 1
            if nxt.isValid() and page(rect.top()) != page(first_line_bottom(nxt, keep) - 1) \
                    and not _breaks_before(b) and rect.height() < page_h * _MAX_KEEP_SHARE:
                # A sub-heading right under a section heading and its intro
                # ("3. ..." + intro + "Before: ...") moves with them.
                lead = _lead_in(b)
                target = lead if lead is not None and not _breaks_before(lead) else b
                found.append((rect.top(), ("block", target.position())))
        elif _CAPTION_RE.match(b.text()) and b.previous().isValid() \
                and _OBJECT_CHAR in b.previous().text():
            # Keep with the figure above, whole: move the figure if its caption
            # would start, or run onto, the next page.
            fig = b.previous()
            frect = lay.blockBoundingRect(fig)
            split = page(rect.top()) != page(rect.bottom() - 1)
            if (page(frect.top()) != page(first_line_bottom(b) - 1) or split) \
                    and not _breaks_before(fig) and frect.height() + rect.height() < page_h * 0.95:
                lead = _lead_in(fig)
                target = lead if lead is not None and not _breaks_before(lead) else fig
                found.append((frect.top(), ("block", target.position())))
        else:
            n_lines = b.layout().lineCount()
            if 1 < n_lines <= _SHORT_PARAGRAPH_LINES and page(rect.top()) != page(rect.bottom() - 1) \
                    and not _breaks_before(b):
                head = _heading_above(b)
                target = head if head is not None and not _breaks_before(head) else b
                found.append((rect.top(), ("block", target.position())))
        b = b.next()

    for start, (top, bottom, table, rows) in tables.items():
        # Its own height, without the gap Qt leaves where it pushed a row to
        # the next page: top to bottom counted that gap, so a table split
        # before its screenshot row looked too tall to move.
        height = sum(r[1] - r[0] for r in rows.values())
        if page(top) == page(bottom - 1) or height > page_h * _MAX_TABLE_SHARE:
            continue
        if table.format().pageBreakPolicy() & _ALWAYS_BEFORE:
            continue
        lead = _lead_in(doc.findBlock(start))
        if lead is not None:
            if not _breaks_before(lead):
                found.append((top, ("block", lead.position())))
            continue
        found.append((top, ("table", start)))
    if not found:
        return None
    return min(found, key=lambda f: f[0])[1]


# A vector figure pushed to the next page is scaled down to fit the gap it
# left instead, when that gap is at least this share of a page and the figure
# keeps at least this share of its size.
_GAP_SHARE = 0.3
_MIN_FIGURE_SCALE = 0.7


def _fit_figures(doc: QTextDocument, page_h: float, max_passes: int = 20) -> int:
    """Shrink vector figures that don't fit under the text above them so they
    fill the rest of the page, caption included, rather than be moved to the
    next page leaving a third or more of this one blank. Returns how many were
    shrunk."""
    lay = doc.documentLayout()
    shrunk = 0
    for _ in range(max_passes):
        fix = None
        b = doc.begin()
        while b.isValid() and fix is None:
            if b.text().strip() == _OBJECT_CHAR and QTextCursor(b).currentTable() is None:
                # Qt lays a figure that doesn't fit out across the page break;
                # keep-together would then move it (and its caption) to the next
                # page, leaving the rest of this one blank.
                rect = lay.blockBoundingRect(b)
                page = int(rect.top() // page_h)
                if int((rect.bottom() - 1) // page_h) != page:
                    gap = (page + 1) * page_h - rect.top()
                    cap = b.next()
                    cap_h = lay.blockBoundingRect(cap).height() if cap.isValid() and \
                        _CAPTION_RE.match(cap.text()) else 0.0
                    scale = (gap - cap_h - 12) / max(1.0, rect.height())
                    if gap >= page_h * _GAP_SHARE and _MIN_FIGURE_SCALE <= scale < 1:
                        fix = (b, scale)
            b = b.next()
        if fix is None:
            break
        block, scale = fix
        cur = QTextCursor(block)
        cur.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
        fmt = cur.charFormat()
        if fmt.objectType() != _OBJECT_TYPE:
            break                       # a plain image, not a vector figure: leave it
        fmt.setProperty(_WIDTH_PROP, float(fmt.property(_WIDTH_PROP)) * scale)
        fmt.setProperty(_HEIGHT_PROP, float(fmt.property(_HEIGHT_PROP)) * scale)
        cur.setCharFormat(fmt)
        _relayout(doc)
        shrunk += 1
    return shrunk


def keep_together(doc: QTextDocument, max_passes: int = 120) -> int:
    """Fix bad page breaks in place (see the module docstring); returns how
    many page breaks were inserted."""
    page_h = doc.pageSize().height()
    if page_h <= 0:
        return 0
    block_fmt = QTextBlockFormat()
    block_fmt.setPageBreakPolicy(_ALWAYS_BEFORE)
    inserted = 0
    _relayout(doc)
    _fit_figures(doc, page_h)
    for _ in range(max_passes):
        fix = _first_violation(doc, page_h)
        if not fix:
            break
        kind, pos = fix
        cur = QTextCursor(doc)
        cur.setPosition(pos)
        if kind == "table" and cur.currentTable() is not None:
            table = cur.currentTable()
            fmt = table.format()
            fmt.setPageBreakPolicy(_ALWAYS_BEFORE)
            table.setFormat(fmt)
        else:
            cur.mergeBlockFormat(block_fmt)
        _relayout(doc)
        inserted += 1
    return inserted
