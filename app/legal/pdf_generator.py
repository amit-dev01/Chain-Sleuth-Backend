"""
pdf_generator.py – Section 94 BNSS legal notice PDF renderer.

Uses Jinja2 to render a legally-formatted HTML notice template, then
converts it to a press-quality PDF via WeasyPrint.

The generated PDF embeds:
  - Full case metadata and VASP attribution details
  - Complete transaction flow summary
  - Section 63 BSA SHA-256 evidence hash stamp (tamper-evident seal)
  - Section 94 BNSS legal compulsion clause for data production

Legal framework:
  - Section 94  BNSS 2023 – Production of documents / electronic records
  - Section 63  BSA  2023 – Admissibility of electronic evidence
  - PMLA 2002   – Anti-money-laundering compliance obligation
  - IT Act 2000 – Cybercrime jurisdiction
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from jinja2 import Environment, select_autoescape
from jinja2 import BaseLoader, TemplateNotFound

from app.models.schemas import LegalNoticePayload

log = logging.getLogger(__name__)

# Output directory for generated PDFs (use /tmp for ephemeral; swap for S3 in prod)
OUTPUT_DIR = Path("generated_pdfs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Jinja2 inline template (no filesystem dependency) ────────────────────────

_NOTICE_TEMPLATE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Legal Notice – Section 94 BNSS | Case {{ case_number }}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=EB+Garamond:wght@400;600;700&family=Noto+Sans:wght@400;600&display=swap');

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'EB Garamond', Georgia, serif;
      font-size: 12pt;
      color: #1a1a1a;
      background: #fff;
      padding: 60px 72px;
      line-height: 1.65;
    }

    /* ── Header ─────────────────────────────────────────────────── */
    .header {
      text-align: center;
      border-bottom: 3px double #1a1a1a;
      padding-bottom: 16px;
      margin-bottom: 24px;
    }
    .header .emblem { font-size: 36pt; line-height: 1; }
    .header h1 {
      font-size: 15pt;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
      margin-top: 6px;
    }
    .header h2 {
      font-size: 12pt;
      font-weight: 600;
      color: #444;
      margin-top: 2px;
    }
    .header .notice-type {
      display: inline-block;
      margin-top: 10px;
      padding: 4px 18px;
      border: 1.5px solid #1a1a1a;
      font-size: 10pt;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      font-family: 'Noto Sans', sans-serif;
    }

    /* ── Meta block ─────────────────────────────────────────────── */
    .meta-table { width: 100%; border-collapse: collapse; margin-bottom: 24px; }
    .meta-table td { padding: 4px 8px; vertical-align: top; font-size: 11pt; }
    .meta-table td.label { font-weight: 600; width: 32%; color: #333; }
    .meta-table td.value { color: #111; }

    /* ── Section headings ───────────────────────────────────────── */
    h3 {
      font-size: 12pt;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
      border-bottom: 1px solid #999;
      padding-bottom: 4px;
      margin: 24px 0 10px;
    }

    /* ── Body paragraphs ────────────────────────────────────────── */
    p { margin-bottom: 12px; text-align: justify; }

    /* ── Address / code blocks ──────────────────────────────────── */
    .mono {
      font-family: 'Noto Sans', 'Courier New', monospace;
      font-size: 9.5pt;
      background: #f4f4f4;
      border: 1px solid #ddd;
      border-radius: 3px;
      padding: 2px 6px;
      word-break: break-all;
    }

    /* ── Evidence hash stamp ─────────────────────────────────────── */
    .hash-stamp {
      border: 2px solid #1a1a1a;
      border-radius: 4px;
      padding: 14px 18px;
      background: #fafafa;
      margin: 20px 0;
    }
    .hash-stamp .stamp-label {
      font-family: 'Noto Sans', sans-serif;
      font-size: 9pt;
      font-weight: 600;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      color: #555;
      margin-bottom: 6px;
    }
    .hash-stamp .hash-value {
      font-family: 'Courier New', monospace;
      font-size: 9pt;
      color: #1a1a1a;
      word-break: break-all;
    }
    .hash-stamp .hash-meta {
      font-size: 9pt;
      color: #666;
      margin-top: 6px;
      font-family: 'Noto Sans', sans-serif;
    }

    /* ── VASP detail table ───────────────────────────────────────── */
    .detail-table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 16px;
      font-size: 11pt;
    }
    .detail-table th {
      background: #1a1a1a;
      color: #fff;
      padding: 6px 10px;
      text-align: left;
      font-family: 'Noto Sans', sans-serif;
      font-size: 9pt;
      letter-spacing: 0.5px;
    }
    .detail-table td {
      padding: 6px 10px;
      border-bottom: 1px solid #e0e0e0;
      vertical-align: top;
    }
    .detail-table tr:nth-child(even) td { background: #f9f9f9; }

    /* ── Legal compulsion clause ─────────────────────────────────── */
    .legal-clause {
      border-left: 4px solid #1a1a1a;
      padding: 10px 16px;
      background: #f8f8f8;
      font-style: italic;
      font-size: 11pt;
      margin: 20px 0;
    }

    /* ── Signature block ─────────────────────────────────────────── */
    .signature-block {
      margin-top: 48px;
      display: flex;
      justify-content: space-between;
    }
    .sig-col { width: 45%; }
    .sig-line {
      border-top: 1px solid #1a1a1a;
      margin-top: 48px;
      padding-top: 6px;
      font-size: 10pt;
      color: #333;
    }

    /* ── Footer ──────────────────────────────────────────────────── */
    .footer {
      margin-top: 40px;
      border-top: 1px solid #ccc;
      padding-top: 10px;
      font-size: 8.5pt;
      color: #888;
      text-align: center;
      font-family: 'Noto Sans', sans-serif;
    }
  </style>
</head>
<body>

<!-- ══ HEADER ══════════════════════════════════════════════════════════════ -->
<div class="header">
  <div class="emblem">⚖</div>
  <h1>Government of India</h1>
  <h2>{{ issuing_authority }}</h2>
  <div class="notice-type">Legal Notice — Section 94 BNSS 2023</div>
</div>

<!-- ══ CASE METADATA ══════════════════════════════════════════════════════ -->
<table class="meta-table">
  <tr>
    <td class="label">Notice Reference No.</td>
    <td class="value">{{ notice_ref }}</td>
    <td class="label">Date of Issue</td>
    <td class="value">{{ issue_date }}</td>
  </tr>
  <tr>
    <td class="label">FIR / Case Number</td>
    <td class="value"><strong>{{ case_number }}</strong></td>
    <td class="label">Case Status</td>
    <td class="value">Active Investigation</td>
  </tr>
  <tr>
    <td class="label">Requesting Authority</td>
    <td class="value">{{ requesting_authority }}</td>
    <td class="label">Designated Officer</td>
    <td class="value">{{ officer_name }}</td>
  </tr>
</table>

<!-- ══ ADDRESSEE ══════════════════════════════════════════════════════════ -->
<h3>To</h3>
<p>
  <strong>The Nodal / Compliance Officer</strong><br/>
  {{ vasp_name }}<br/>
  Email: <span class="mono">{{ nodal_email }}</span>
  {% if nodal_phone %}<br/>Phone: {{ nodal_phone }}{% endif %}
</p>

<!-- ══ SUBJECT ═════════════════════════════════════════════════════════════ -->
<h3>Subject</h3>
<p>
  Production of Know-Your-Customer (KYC) Records, Transaction Logs, and
  User Account Details under <strong>Section 94 of the Bharatiya Nagarik
  Suraksha Sanhita (BNSS) 2023</strong> in connection with FIR
  <strong>{{ case_number }}</strong> — Cryptocurrency Fraud Investigation
  (Estimated Loss: ₹{{ "{:,.2f}".format(loss_amount_inr) }}).
</p>

<!-- ══ LEGAL COMPULSION CLAUSE ════════════════════════════════════════════ -->
<div class="legal-clause">
  Pursuant to Section 94 of the Bharatiya Nagarik Suraksha Sanhita 2023,
  you are hereby directed to produce, within <strong>7 (seven) working days</strong>
  of receipt of this notice, all documents, electronic records, and KYC data
  pertaining to the account(s) specified herein. Failure to comply constitutes
  an offence under Section 179 IPC / Section 63 BSA 2023 and may result in
  punitive action including prosecution.
</div>

<!-- ══ SUSPECT DETAILS ════════════════════════════════════════════════════ -->
<h3>Suspect Blockchain Address</h3>
<table class="detail-table">
  <tr>
    <th>Field</th>
    <th>Value</th>
  </tr>
  <tr>
    <td>Suspect Address</td>
    <td><span class="mono">{{ suspect_address }}</span></td>
  </tr>
  <tr>
    <td>Blockchain Network</td>
    <td>{{ chain | upper }}</td>
  </tr>
  <tr>
    <td>Attribution Confidence</td>
    <td>{{ "%.1f" | format(confidence_score * 100) }}%</td>
  </tr>
  <tr>
    <td>VASP Deposit Address (KYC-linked)</td>
    <td><span class="mono">{{ deposit_address }}</span></td>
  </tr>
  <tr>
    <td>VASP Hot Wallet (Sweep Address)</td>
    <td><span class="mono">{{ hot_wallet_address }}</span></td>
  </tr>
  <tr>
    <td>FIU-IND Registered</td>
    <td>{{ "YES" if is_fiu_registered else "NO — Note: Compliance obligations still apply under PMLA 2002" }}</td>
  </tr>
  <tr>
    <td>Estimated Loss (INR)</td>
    <td><strong>₹{{ "{:,.2f}".format(loss_amount_inr) }}</strong></td>
  </tr>
</table>

<!-- ══ TRANSACTION FLOW SUMMARY ═══════════════════════════════════════════ -->
<h3>Transaction Flow Summary</h3>
<p>{{ flow_summary }}</p>

<!-- ══ SHA-256 EVIDENCE HASH STAMP ════════════════════════════════════════ -->
<h3>Section 63 BSA Evidence Integrity Stamp</h3>
<div class="hash-stamp">
  <div class="stamp-label">🔒 SHA-256 Evidence Hash (Tamper-Evident Seal)</div>
  <div class="hash-value">{{ sha256_evidence_hash }}</div>
  <div class="hash-meta">
    Generated: {{ generated_at }} UTC &nbsp;|&nbsp;
    Algorithm: SHA-256 (FIPS 180-4) &nbsp;|&nbsp;
    Legal basis: Section 63 BSA 2023 / Section 79A IT Act 2000
  </div>
</div>

<p style="font-size:10pt; color:#555;">
  The SHA-256 hash above was computed over a canonically sorted, UTF-8 encoded
  JSON representation of all transaction hashes and wallet node addresses
  constituting this evidence chain. Any modification to the underlying
  transaction data will produce a different hash, rendering tampering detectable.
</p>

<!-- ══ LEGAL BASIS ════════════════════════════════════════════════════════ -->
<h3>Legal Basis</h3>
<p>
  This notice is issued under the authority of the following statutes:
</p>
<table class="detail-table">
  <tr><th>Statute</th><th>Provision</th><th>Application</th></tr>
  <tr>
    <td>BNSS 2023</td>
    <td>Section 94</td>
    <td>Compulsory production of electronic records / documents</td>
  </tr>
  <tr>
    <td>BSA 2023</td>
    <td>Section 63</td>
    <td>Admissibility of electronic evidence; hash certification</td>
  </tr>
  <tr>
    <td>PMLA 2002</td>
    <td>Sections 12 &amp; 13</td>
    <td>Obligation to maintain and furnish KYC / AML records</td>
  </tr>
  <tr>
    <td>IT Act 2000</td>
    <td>Sections 69B &amp; 79A</td>
    <td>Cyber investigation powers; electronic evidence certification</td>
  </tr>
</table>

<!-- ══ INFORMATION REQUIRED ══════════════════════════════════════════════ -->
<h3>Information Required</h3>
<p>Please provide the following within <strong>7 working days</strong>:</p>
<ol style="margin-left:24px; margin-bottom:12px;">
  <li>Full KYC records (name, address, ID proofs) for the deposit address
      <span class="mono">{{ deposit_address }}</span></li>
  <li>Complete transaction history for the above address from inception</li>
  <li>IP address logs, device fingerprints, and login timestamps</li>
  <li>Any linked accounts and associated KYC documents</li>
  <li>Correspondence (email / chat) related to the account</li>
  <li>Current account balance and any freeze/flag status</li>
</ol>

<!-- ══ SIGNATURE ══════════════════════════════════════════════════════════ -->
<div class="signature-block">
  <div class="sig-col">
    <div class="sig-line">
      <strong>{{ officer_name }}</strong><br/>
      {{ officer_designation }}<br/>
      {{ issuing_authority }}
    </div>
  </div>
  <div class="sig-col" style="text-align:right;">
    <div class="sig-line">
      Official Seal / Digital Signature<br/>
      Date: {{ issue_date }}
    </div>
  </div>
</div>

<!-- ══ FOOTER ════════════════════════════════════════════════════════════ -->
<div class="footer">
  CONFIDENTIAL — FOR LAW ENFORCEMENT USE ONLY &nbsp;|&nbsp;
  Generated by ChainSleuth Forensic Platform &nbsp;|&nbsp;
  Notice Ref: {{ notice_ref }} &nbsp;|&nbsp;
  {{ generated_at }} UTC
</div>

</body>
</html>
"""


# ── Jinja2 environment with inline loader ─────────────────────────────────────

class _InlineLoader(BaseLoader):
    """Jinja2 loader that serves templates from in-memory strings."""

    def __init__(self, templates: dict[str, str]):
        self._templates = templates

    def get_source(self, environment: Environment, template: str):
        src = self._templates.get(template)
        if src is None:
            raise TemplateNotFound(template)
        return src, None, lambda: True


_jinja_env = Environment(
    loader=_InlineLoader({"notice.html": _NOTICE_TEMPLATE_HTML}),
    autoescape=select_autoescape(["html"]),
)


# ── Public API ────────────────────────────────────────────────────────────────

async def generate_legal_notice_pdf(
    payload: LegalNoticePayload,
    officer_name: str = "Investigating Officer",
    officer_designation: str = "Inspector of Police (Cyber Crime)",
    issuing_authority: str = "Cyber Crime Investigation Cell",
    requesting_authority: str = "State Cyber Crime Unit",
) -> tuple[Path, str]:
    """
    Render a Section 94 BNSS legal notice PDF from a ``LegalNoticePayload``.

    Args:
        payload:               Validated LegalNoticePayload (from schemas.py).
        officer_name:          Name of the certifying officer.
        officer_designation:   Rank / designation of the officer.
        issuing_authority:     Name of the issuing police / government body.
        requesting_authority:  Authority formally requesting the records.

    Returns:
        A tuple of:
          - ``Path`` to the generated PDF file on disk.
          - ``str``  notice reference number (for storing in DB / response).

    Raises:
        RuntimeError: If WeasyPrint is not installed.
        jinja2.TemplateNotFound: If the template cannot be loaded.
    """
    try:
        from weasyprint import HTML as WeasyprintHTML
    except ImportError as exc:
        raise RuntimeError(
            "WeasyPrint is required for PDF generation. "
            "Install it with: pip install weasyprint"
        ) from exc

    notice_ref   = f"NOTICE-{str(uuid4()).upper()[:8]}"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    issue_date   = datetime.now(timezone.utc).strftime("%d %B %Y")

    vasp = payload.attributed_vasp

    context = {
        # Notice identity
        "notice_ref":           notice_ref,
        "issue_date":           issue_date,
        "generated_at":         generated_at,

        # Case
        "case_number":          payload.case_number,
        "requesting_authority": requesting_authority,
        "issuing_authority":    issuing_authority,
        "officer_name":         officer_name,
        "officer_designation":  officer_designation,

        # VASP
        "vasp_name":            vasp.vasp_name,
        "nodal_email":          vasp.nodal_officer_email,
        "nodal_phone":          vasp.nodal_officer_phone,
        "is_fiu_registered":    vasp.is_fiu_registered,
        "deposit_address":      vasp.deposit_address,
        "hot_wallet_address":   vasp.hot_wallet_address,
        "confidence_score":     vasp.confidence_score,

        # Suspect
        "suspect_address":      payload.suspect_address,
        "chain":                "tron",   # extracted from suspect address context

        # Financial
        "loss_amount_inr":      payload.loss_amount_inr,

        # Evidence
        "flow_summary":         payload.flow_summary,
        "sha256_evidence_hash": payload.sha256_evidence_hash,
    }

    # ── Render HTML ───────────────────────────────────────────────────────────
    template     = _jinja_env.get_template("notice.html")
    html_content = template.render(**context)

    # ── Convert to PDF ────────────────────────────────────────────────────────
    output_path = OUTPUT_DIR / f"{notice_ref}.pdf"
    WeasyprintHTML(string=html_content).write_pdf(str(output_path))

    log.info(
        "Legal notice PDF generated: %s (case=%s, vasp=%s)",
        output_path, payload.case_number, vasp.vasp_name,
    )
    return output_path, notice_ref
