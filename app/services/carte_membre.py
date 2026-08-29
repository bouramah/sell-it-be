"""Génération de la carte de membre « Aide Humanitaire » — un PDF de 2 pages au format carte
(CR80, ~85.6mm x 54mm) : recto (identité, n° de membre, établissement, QR) puis verso (conditions
d'utilisation, contact KFSTORE, QR). Réutilise le rendu HTML→PDF partagé (WeasyPrint) et le logo
déjà encodés dans app/services/pdf.py, mais avec un gabarit dédié (le gabarit A4 de pdf.py est
pensé pour les factures/bons de commande, pas pour un format carte).

Mise en page volontairement en tables plutôt qu'en flexbox : à cette échelle (quelques mm), un
flex combiné à des éléments positionnés en absolu fait déborder le contenu sur une page
supplémentaire sous WeasyPrint — les tables donnent un calcul de hauteur fiable."""
import base64
from html import escape
from io import BytesIO

import qrcode

from app.services.pdf import _LOGO_DATA_URI, render_pdf

_STYLE = """
@page { size: 85.6mm 54mm; margin: 0; }
body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #0f172a; font-size: 6pt; margin: 0; }
.card { width: 85.6mm; height: 54mm; overflow: hidden; box-sizing: border-box; position: relative; }
.card + .card { page-break-before: always; }
.band { background: #0f172a; color: #fff; padding: 1mm 3mm; }
.band table { width: 100%; border-collapse: collapse; }
.brand img { height: 4.5mm; display: block; }
.brand-text { font-size: 7.5pt; font-weight: bold; line-height: 1.1; }
.brand-sub { font-size: 4pt; color: #cbd5e1; letter-spacing: 0.04em; }
.badge { background: #f5b400; color: #0f172a; font-size: 5pt; font-weight: bold; padding: 0.6mm 2mm; border-radius: 2.5mm; white-space: nowrap; }
.body-table { width: 100%; border-collapse: collapse; margin-top: 1.5mm; }
.body-table td { vertical-align: top; padding: 0; }
.photo-cell { width: 12mm; padding-right: 2mm; }
.photo-box { width: 11mm; height: 13mm; border: 0.5px dashed #cbd5e1; border-radius: 0.5mm; text-align: center; vertical-align: middle; color: #94a3b8; font-size: 4pt; }
.label { font-size: 4pt; text-transform: uppercase; letter-spacing: 0.04em; color: #94a3b8; margin: 0; padding-top: 0.8mm; }
.value { font-size: 6pt; font-weight: bold; margin: 0; border-bottom: 0.5px dotted #cbd5e1; }
.bottom-row td { vertical-align: bottom; padding: 0 3mm; }
.qr { width: 9mm; height: 9mm; display: block; }
.footer-band { position: absolute; left: 0; right: 0; bottom: 0; background: #0f172a; color: #f5b400; font-size: 4.5pt; font-weight: bold; text-align: center; padding: 1mm 2mm; }
.back-title { font-size: 6pt; font-weight: bold; color: #0f172a; margin: 0 0 1mm; }
.conditions { font-size: 4.3pt; line-height: 1.35; color: #334155; margin: 0; padding-left: 2.5mm; }
.conditions li { margin-bottom: 0.6mm; }
.contact { font-size: 4.3pt; color: #334155; line-height: 1.35; }
.numero { font-size: 4.5pt; color: #64748b; }
"""


def _qr_data_uri(data: str) -> str:
    img = qrcode.make(data)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def generer_carte_membre_pdf(*, nom_complet: str, numero_membre: str, etablissement_nom: str, type_etablissement: str) -> bytes:
    qr = _qr_data_uri(numero_membre)
    brand_html = f'<img src="{_LOGO_DATA_URI}" alt="KFSTORE" />' if _LOGO_DATA_URI else '<div class="brand-text">KFSTORE</div>'

    recto = f"""
    <div class="card">
      <div class="band">
        <table><tr>
          <td class="brand">{brand_html}</td>
          <td style="padding-left:2mm"><div class="brand-text">KF STORE</div><div class="brand-sub">BY GROUPE SKF</div></td>
          <td style="text-align:right"><span class="badge">AIDE HUMANITAIRE</span></td>
        </tr></table>
      </div>
      <div style="padding: 0 3mm;">
        <table class="body-table"><tr>
          <td class="photo-cell"><div class="photo-box">PHOTO</div></td>
          <td>
            <p class="label">Nom et prénom</p><p class="value">{escape(nom_complet)}</p>
            <p class="label">N° de membre</p><p class="value">{escape(numero_membre)}</p>
            <p class="label">Établissement</p><p class="value">{escape(etablissement_nom)}</p>
          </td>
        </tr></table>
        <table class="bottom-row" style="width:100%; margin-top: 1mm;"><tr>
          <td><p class="label" style="padding-top:0">Secteur</p><p class="value">{escape(type_etablissement)}</p></td>
          <td style="width:11mm; text-align:right;"><img class="qr" src="{qr}" /></td>
        </tr></table>
      </div>
      <div class="footer-band">Membre du groupe KFSTORE AIDE HUMANITAIRE</div>
    </div>
    """

    verso = f"""
    <div class="card">
      <div style="padding: 3mm;">
        <p class="back-title">CONDITIONS D'UTILISATION</p>
        <ul class="conditions">
          <li>Carte personnelle, incessible et non transférable à un tiers.</li>
          <li>À présenter obligatoirement en boutique lors de tout retrait au titre du crédit alimentaire garanti « KFSTORE AIDE Humanitaire ».</li>
          <li>En cas de perte ou de vol, signaler immédiatement à KFSTORE et à l'établissement de rattachement.</li>
          <li>L'usage du crédit est strictement limité à l'acquisition de denrées alimentaires dans les boutiques KFSTORE.</li>
        </ul>
        <table style="width:100%; margin-top: 1.5mm;"><tr>
          <td class="contact">
            <strong>Contact KFSTORE</strong><br/>
            Lansanaya Magasin, sur la déviation — Conakry<br/>
            Tél : 500224 | 620191920 | 626404015 | 625950404
          </td>
          <td style="width:11mm; text-align:right; vertical-align:bottom;"><img class="qr" src="{qr}" /></td>
        </tr></table>
        <p class="numero">{escape(numero_membre)}</p>
      </div>
    </div>
    """

    html = f"""
    <html>
    <head><meta charset="utf-8"><style>{_STYLE}</style></head>
    <body>{recto}{verso}</body>
    </html>
    """
    return render_pdf(html)
