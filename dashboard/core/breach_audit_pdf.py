"""Renders a core.breach_audit.BreachAuditData to a PDF: an attacker's-eye
hardening audit -- which breakout, isolation and whitelist-bypass attempts the
platform blocked, and which (if any) it did not.

GUI-thread only, same print machinery and Baskerville styling as
core/pool_test_report_pdf.py.
"""
from __future__ import annotations

from PyQt6.QtCore import QMarginsF, QSizeF
from PyQt6.QtGui import QColor, QFont, QPageLayout, QPageSize, QPen, QTextDocument
from PyQt6.QtPrintSupport import QPrinter

from core import diagrams, honeypot_layer, report_pagination, vector_figures
from core.diagrams import _arrow, _box, _label, _new
from core.pattern_report_pdf import (_FONT_CSS_STACK, _GREEN, _GREY, _ORANGE, _RED,
                                     _badge, _esc, _report_font_family)
from core.breach_audit import (CAT_BREAKOUT, CAT_EDGE, CAT_PROD_NET, CAT_WHITELIST,
                               CATEGORY_INTRO, CATEGORY_LABELS, CRITICAL, ERROR, FAIL,
                               HIGH, MEDIUM, PASS, SKIP, WARN, BreachAuditData, ProbeResult)

_OUTCOME_COLOR = {PASS: _GREEN, FAIL: _RED, WARN: _ORANGE, SKIP: _GREY, ERROR: _GREY}
_OUTCOME_LABEL = {PASS: "PASS", FAIL: "FAIL", WARN: "WARN", SKIP: "SKIP", ERROR: "ERROR"}
_SEV_COLOR = {CRITICAL: _RED, HIGH: _ORANGE, MEDIUM: _GREY}


def _outcome_badge(outcome: str) -> str:
    return _badge(_OUTCOME_LABEL.get(outcome, outcome.upper()),
                  _OUTCOME_COLOR.get(outcome, _GREY))


def _probe_table(results: list[ProbeResult]) -> str:
    if not results:
        return '<p style="color:#555;">No probes ran in this category.</p>'
    rows = [
        '<table width="100%" cellpadding="4" cellspacing="0" border="1" '
        'style="border-collapse:collapse; border-color:#ddd; font-size:9pt;">',
        '<tr style="background-color:#f0f0f0;">'
        '<th align="left" width="16%">Result</th>'
        '<th align="left" width="34%">Probe</th>'
        '<th align="left" width="28%">Expected</th>'
        '<th align="left" width="22%">Evidence</th></tr>',
    ]
    for r in results:
        sev = ""
        if r.outcome in (FAIL, WARN):
            sev = (f' <span style="color:{_SEV_COLOR.get(r.severity, _GREY)};">'
                   f'[{_esc(r.severity)}]</span>')
        src = f'<br/><span style="color:#999;">from {_esc(r.source)}</span>' if r.source else ""
        rows.append(
            "<tr>"
            f'<td>{_outcome_badge(r.outcome)}{sev}</td>'
            f'<td>{_esc(r.probe)}{src}</td>'
            f'<td style="color:#555;">{_esc(r.expectation)}</td>'
            f'<td style="color:#555;">{_esc(r.evidence)}</td>'
            "</tr>")
    rows.append("</table>")
    return "".join(rows)


def summary_figure(data: BreachAuditData, family: str = "Serif"):
    """A bar per category: PASS (green) / WARN (orange) / FAIL (red) counts,
    so the reader sees at a glance where any hole is."""
    cats = [c for c in (CAT_BREAKOUT, CAT_PROD_NET, CAT_WHITELIST, CAT_EDGE)
            if c in data.categories]
    row_h = 54
    img, p = _new(820, 60 + max(1, len(cats)) * row_h)
    p.setFont(QFont(family, 12, QFont.Weight.Bold))
    p.setPen(QColor("#1a1a1a"))
    p.drawText(20, 26, "Probes per category: passed vs. failed")
    y = 52
    bar_x, bar_w = 300, 480
    for c in cats:
        rs = data.by_category(c)
        total = len(rs) or 1
        counts = {PASS: 0, WARN: 0, FAIL: 0, SKIP: 0, ERROR: 0}
        for r in rs:
            counts[r.outcome] = counts.get(r.outcome, 0) + 1
        p.setFont(QFont(family, 10))
        p.setPen(QColor("#1a1a1a"))
        p.drawText(20, y + 22, CATEGORY_LABELS.get(c, c))
        x = bar_x
        for outcome, color in ((PASS, _GREEN), (WARN, _ORANGE), (FAIL, _RED),
                               (SKIP, "#cfd4da"), (ERROR, "#cfd4da")):
            n = counts.get(outcome, 0)
            if n == 0:
                continue
            w = int(bar_w * n / total)
            p.fillRect(x, y + 6, w, 26, QColor(color))
            if w > 20:
                p.setPen(QColor("#ffffff"))
                p.setFont(QFont(family, 9, QFont.Weight.Bold))
                p.drawText(x + 4, y + 24, str(n))
            x += w
        p.setPen(QPen(QColor("#999999")))
        p.drawRect(bar_x, y + 6, bar_w, 26)
        y += row_h
    p.end()
    return img


def topology_figure(family: str = "Serif"):
    """What the breakout probes assert: a honeypot pool is a sealed box with no
    arrow out to production, the other pools, the Docker daemon or the
    internet."""
    img, p = _new(820, 300)
    p.setFont(QFont(family, 12, QFont.Weight.Bold))
    p.setPen(QColor("#1a1a1a"))
    p.drawText(20, 24, "Every arrow out of a honeypot pool must be blocked")

    hp = _box(p, 40, 110, 210, 70, "Honeypot pool", "(attacker-owned)",
              fill="#c62828", text="#ffffff")
    net = _box(p, 560, 20, 220, 40, "open internet", fill="#555555", text="#ffffff")
    prod = _box(p, 560, 80, 220, 50, "production shop + DB", fill="#2e7d32", text="#ffffff")
    peers = _box(p, 560, 150, 220, 50, "other honeypot pools", fill="#e08a00", text="#ffffff")
    dock = _box(p, 560, 220, 220, 50, "Docker daemon / host", fill="#555555", text="#ffffff")
    for dest in (net, prod, peers, dock):
        _arrow(p, hp[0] + 105, hp[1], dest[0] - 110, dest[1], color="#c62828", dashed=True)
        _label(p, (hp[0] + dest[0]) / 2, (hp[1] + dest[1]) / 2 - 8, "blocked", color="#c62828")
    p.setFont(QFont(family, 9))
    p.setPen(QColor("#555555"))
    p.drawText(40, 205, "Inbound exploitation is allowed by design;")
    p.drawText(40, 220, "outbound pivoting is not.")
    p.end()
    return img


def render_pdf(data: BreachAuditData, out_path: str) -> None:
    family = _report_font_family()
    status, summary = data.headline()
    status_color = _RED if status.startswith("BREACH") else (
        _ORANGE if "warning" in status.lower() else _GREEN)
    counts = data.counts()
    layer_label = honeypot_layer.layer(data.honeypot_layer).short_label

    doc = QTextDocument()
    doc.setDefaultFont(QFont(family, 11))

    parts = [
        f'<div style="font-family: {_FONT_CSS_STACK};">',
        '<h1 style="color:#222;">Breach Validation report</h1>',
        '<table width="100%" style="color:#555;"><tr><td>'
        f'Generated: {_esc(data.generated_at)}<br/>'
        f'Target: {_esc(data.target_label)} &nbsp; ({_esc(data.base_url)})<br/>'
        f'Honeypot layer: {_esc(layer_label)}<br/>'
        f'Categories: {_esc(", ".join(CATEGORY_LABELS.get(c, c) for c in data.categories))}<br/>'
        + (f'Honeypot pools scanned: {_esc(", ".join(str(p) for p in data.pools_scanned))}<br/>'
           if data.pools_scanned else '')
        + '</td></tr></table><hr/>',
        '<h2 style="color:#222;">Result</h2>',
        f'<p>{_badge(status, status_color)} &nbsp;<b>{_esc(summary)}</b></p>',
        '<p style="color:#555;">'
        f'{counts[PASS]} passed &middot; {counts[FAIL]} failed &middot; '
        f'{counts[WARN]} warnings &middot; {counts[SKIP]} skipped &middot; '
        f'{counts[ERROR]} errored.</p>',
    ]

    if data.notes:
        parts.append('<ul style="color:#c62828;">'
                     + "".join(f"<li>{_esc(n)}</li>" for n in data.notes) + '</ul>')

    # Breaches first, called out explicitly.
    breaches = data.breaches
    if breaches:
        parts.append('<h2 style="color:#c62828;">Hardening holes found</h2>')
        items = []
        for r in sorted(breaches, key=lambda x: {CRITICAL: 0, HIGH: 1, MEDIUM: 2}.get(x.severity, 9)):
            src = f" (from {_esc(r.source)})" if r.source else ""
            items.append(f'<li><b>[{_esc(r.severity)}]</b> {_esc(r.probe)}{src} '
                         f'&mdash; {_esc(r.evidence)}</li>')
        parts.append('<ul>' + "".join(items) + '</ul>')
    else:
        parts.append('<p style="color:#2e7d32;"><b>No hardening holes were found by the '
                     'probes that ran.</b></p>')

    parts.append('<h2 style="color:#222;">What is being tested</h2>')
    parts.append(
        '<p style="color:#555;">This report takes the attacker\'s side. Where the '
        'Attack Simulation page proves exploit traffic is diverted and the Segmentation '
        'Validation page proves diverted sessions are isolated, these probes assume the '
        'attacker has already won a honeypot or is probing the edge, and try to break '
        'the containment: climb out of a honeypot container, reach the production network '
        'from the wrong side, or smuggle a honeypot target past the whitelist onto '
        'production. Every probe is read-only. A blocked connection is a PASS &ndash; it '
        'is a dead end the attacker cannot use.</p>')

    parts.append(diagrams.figure_html(
        doc, summary_figure(data, family), "breach-summary", 1,
        "Probes per category. Green passed (the hardening held), orange is a weaker-than-"
        "ideal warning, red is a breach. Grey covers skipped or inconclusive probes.",
        width=640))

    # Per-category sections.
    fig_n = 2
    for cat in (CAT_BREAKOUT, CAT_PROD_NET, CAT_WHITELIST, CAT_EDGE):
        if cat not in data.categories:
            continue
        parts.append(f'<h2 style="color:#222;">{_esc(CATEGORY_LABELS[cat])}</h2>')
        parts.append(f'<p style="color:#555;">{_esc(CATEGORY_INTRO[cat])}</p>')
        if cat == CAT_BREAKOUT:
            parts.append(diagrams.figure_html(
                doc, topology_figure(family), "breach-topology", fig_n,
                "The containment the breakout probes assert: a compromised honeypot pool "
                "has no working route out to production, its peers, the Docker control "
                "plane or the internet.", width=640))
            fig_n += 1
        parts.append(_probe_table(data.by_category(cat)))

    parts.append('</div>')
    doc.setHtml("<body>" + "".join(parts) + "</body>")
    vector_figures.embed_figures(doc)

    printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(out_path)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    doc.setPageSize(QSizeF(printer.pageRect(QPrinter.Unit.DevicePixel).size()))
    report_pagination.keep_together(doc)
    doc.print(printer)
