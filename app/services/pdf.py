import os
import platform
from datetime import datetime
from html import escape

if platform.system() == "Darwin":
    for _path in ("/opt/homebrew/lib", "/usr/local/lib"):
        if os.path.isdir(_path):
            os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "") + os.pathsep + _path

from weasyprint import HTML  # noqa: E402

STYLE = """
@page { size: A4; margin: 2cm; }
body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #1e293b; font-size: 11pt; }
.header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #0f766e; padding-bottom: 12px; margin-bottom: 20px; }
.brand { font-size: 20pt; font-weight: bold; color: #0f766e; }
.brand-sub { font-size: 9pt; color: #64748b; }
.doc-title { text-align: right; }
.doc-title h1 { font-size: 16pt; margin: 0; color: #0f172a; }
.doc-title .ref { font-size: 10pt; color: #64748b; }
.meta { display: flex; justify-content: space-between; margin-bottom: 20px; }
.meta .block { width: 47%; }
.meta .label { font-size: 8pt; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; margin-bottom: 4px; }
.meta .name { font-weight: bold; font-size: 12pt; }
.meta .line { font-size: 10pt; color: #475569; }
table.articles { width: 100%; border-collapse: collapse; margin-top: 10px; }
table.articles th { text-align: left; font-size: 8pt; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; border-bottom: 2px solid #cbd5e1; padding: 6px 4px; }
table.articles td { padding: 8px 4px; border-bottom: 1px solid #e2e8f0; font-size: 10pt; }
table.articles .num { text-align: right; }
.totals { margin-top: 14px; display: flex; justify-content: flex-end; }
.totals table { border-collapse: collapse; }
.totals td { padding: 4px 10px; font-size: 10.5pt; }
.totals .grand td { font-weight: bold; font-size: 13pt; border-top: 2px solid #0f766e; color: #0f766e; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 999px; background: #ccfbf1; color: #0f766e; font-size: 9pt; font-weight: bold; }
.footer { margin-top: 40px; padding-top: 12px; border-top: 1px solid #e2e8f0; font-size: 8pt; color: #94a3b8; }
.signatures { margin-top: 50px; display: flex; justify-content: space-between; }
.signatures .box { width: 45%; border-top: 1px solid #94a3b8; padding-top: 6px; font-size: 9pt; color: #64748b; }
"""


def render_pdf(html: str) -> bytes:
    return HTML(string=html).write_pdf()


def document_shell(
    *,
    doc_title: str,
    reference: str,
    date_str: str,
    statut_label: str | None,
    de_label: str,
    de_lignes: list[str],
    a_label: str,
    a_lignes: list[str],
    body_html: str,
    signatures: tuple[str, str] | None = None,
) -> str:
    statut_html = f'<span class="badge">{escape(statut_label)}</span>' if statut_label else ""
    de_html = "".join(f'<div class="line">{escape(l)}</div>' for l in de_lignes if l)
    a_html = "".join(f'<div class="line">{escape(l)}</div>' for l in a_lignes if l)
    signatures_html = ""
    if signatures:
        signatures_html = f"""
        <div class="signatures">
          <div class="box">{escape(signatures[0])}</div>
          <div class="box">{escape(signatures[1])}</div>
        </div>
        """
    return f"""
    <html>
    <head><meta charset="utf-8"><style>{STYLE}</style></head>
    <body>
      <div class="header">
        <div>
          <div class="brand">KFSTORE</div>
          <div class="brand-sub">GROUPE SKF SARL</div>
        </div>
        <div class="doc-title">
          <h1>{escape(doc_title)}</h1>
          <div class="ref">{escape(reference)} — {escape(date_str)}</div>
          <div style="margin-top:4px">{statut_html}</div>
        </div>
      </div>
      <div class="meta">
        <div class="block">
          <div class="label">{escape(de_label)}</div>
          {de_html}
        </div>
        <div class="block">
          <div class="label">{escape(a_label)}</div>
          {a_html}
        </div>
      </div>
      {body_html}
      {signatures_html}
      <div class="footer">
        Document généré automatiquement par KFSTORE le {datetime.now().strftime('%d/%m/%Y à %H:%M')}.
      </div>
    </body>
    </html>
    """


def articles_table(rows: list[dict], montant_col_label: str = "Sous-total", extra_col: str | None = None) -> str:
    extra_header = f"<th>{escape(extra_col)}</th>" if extra_col else ""
    body = ""
    for r in rows:
        extra_cell = f"<td class=\"num\">{r.get('extra', '')}</td>" if extra_col else ""
        body += f"""
        <tr>
          <td>{escape(str(r['produit']))}</td>
          <td class="num">{r['quantite']}</td>
          <td class="num">{r['prix_unitaire']}</td>
          {extra_cell}
          <td class="num">{r['sous_total']}</td>
        </tr>
        """
    return f"""
    <table class="articles">
      <thead>
        <tr>
          <th>Produit</th>
          <th class="num">Quantité</th>
          <th class="num">Prix unitaire</th>
          {extra_header}
          <th class="num">{escape(montant_col_label)}</th>
        </tr>
      </thead>
      <tbody>{body}</tbody>
    </table>
    """


def totals_block(rows: list[tuple[str, str]], grand_label: str, grand_value: str) -> str:
    lines = "".join(f'<tr><td>{escape(label)}</td><td class="num">{escape(value)}</td></tr>' for label, value in rows)
    return f"""
    <div class="totals">
      <table>
        {lines}
        <tr class="grand"><td>{escape(grand_label)}</td><td class="num">{escape(grand_value)}</td></tr>
      </table>
    </div>
    """
