"""Generate an evidence-focused PDF from the existing forensic analyzers.

Install: pip install reportlab
No detector code is changed by this module.
"""

from datetime import datetime, timezone
import hashlib
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as PDFImage,
    KeepTogether,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line

from modules.ela import analyze_ela
from modules.metadata import extract_metadata
from modules.noise import analyze_noise
from modules.copy_move import detect_copy_move
from modules.double_jpeg import analyze_double_jpeg

NAVY = colors.HexColor("#0B1220")
TEAL = colors.HexColor("#007F75")
INK = colors.HexColor("#1B2938")
MUTED = colors.HexColor("#536579")
PALE = colors.HexColor("#F1F6F9")
BORDER = colors.HexColor("#D8E3EA")


def safe(value):
    """Turn image-derived text into safe ReportLab paragraph content."""
    value = str(value).replace("\n", " ").replace("\r", " ")
    value = "".join(ch if ord(ch) >= 32 else " " for ch in value)
    return escape(value.encode("latin-1", "replace").decode("latin-1"))


def photo(image, width=485, max_height=235):
    """Bound images in the PDF without saving any evidence to disk."""
    img = ImageOps.exif_transpose(image).convert("RGB")
    img.thumbnail((1100, 850))
    w, h = img.size
    ratio = min(width / w, max_height / h)
    stream = BytesIO()
    img.save(stream, format="PNG")
    stream.seek(0)
    return PDFImage(stream, width=w * ratio, height=h * ratio)


def histogram(result):
    """Compact, dependency-free bar chart of AC coefficient counts."""
    d = Drawing(500, 165)
    data = result["histogram_counts"]
    bins = result["histogram_bins"]
    left, base, plot_w, plot_h = 38, 25, 452, 115
    d.add(Line(left, base, left + plot_w, base, strokeColor=MUTED))
    d.add(Line(left, base, left, base + plot_h, strokeColor=MUTED))
    ceiling = max(max(data), 1)
    bar_w = plot_w / len(data)
    for i, count in enumerate(data):
        bar_h = (count / ceiling) * plot_h
        d.add(Rect(left + i * bar_w + 1, base,
                   max(1, bar_w - 2), bar_h,
                   strokeColor=None, fillColor=TEAL))
        if bins[i] in (-12, -8, -4, 0, 4, 8, 12):
            d.add(String(left + (i + .5) * bar_w, 11, str(bins[i]),
                         textAnchor="middle", fontSize=8, fillColor=MUTED))
    d.add(String(left + 4, 146, "Max count: " + str(ceiling), fontSize=9, fillColor=MUTED))
    return d


def generate_pdf_report(file_bytes, filename, image, reviewer_verdict="Not assessed"):
    """Return PDF bytes; original file bytes are never changed."""
    digest = hashlib.sha256(file_bytes).hexdigest()
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Call the current modules exactly as used by the Streamlit dashboard.
    ela = analyze_ela(image)
    metadata = extract_metadata(image)
    noise_heatmap, noise_overlay, noise_stats = analyze_noise(image)
    copy_image, copy_stats = detect_copy_move(image)
    jpeg = analyze_double_jpeg(file_bytes) if image.format == "JPEG" else {
        "supported": False, "reason": "Not applicable: source is not JPEG."
    }

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=46, rightMargin=46, topMargin=50, bottomMargin=52,
        title="Image Forensics Evidence Report", author="Digital Evidence Lab",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="BigTitleDEL", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=21, leading=27, textColor=NAVY, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="HeadingDEL", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=13, leading=17, textColor=TEAL, spaceBefore=16, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="BodyDEL", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=9, leading=14, textColor=INK, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="SmallDEL", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=8, leading=11, textColor=MUTED, spaceAfter=5,
    ))

    story = []
    P = lambda val, style="BodyDEL": Paragraph(safe(val), styles[style])

    def heading(value):
        story.append(P(value, "HeadingDEL"))

    def grid(rows, widths=(155, 346)):
        result = Table([[P(k, "SmallDEL"), P(v)] for k, v in rows],
                       colWidths=list(widths), hAlign="LEFT", repeatRows=0)
        result.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [PALE, colors.white]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(result)

    story.append(P("DIGITAL EVIDENCE LAB", "SmallDEL"))
    story.append(P("IMAGE FORENSICS REPORT", "BigTitleDEL"))
    story.append(P("Generated: " + generated + " | Reference: " + digest[:12].upper(), "SmallDEL"))
    story.append(P("Automated indicators with a reviewer-selected assessment, not a proof of editing."))

    heading("01 / Evidence record")
    grid([
        ("Source file", Path(filename).name),
        ("Image format", image.format or "Unknown"),
        ("Pixel dimensions", f"{image.width} x {image.height}"),
        ("Original file size", f"{len(file_bytes):,} bytes"),
        ("Reviewer selection", reviewer_verdict + " (not algorithm-generated)"),
    ])
    story.append(Spacer(1, 7))
    story.append(P("SHA-256 of the original uploaded file:", "SmallDEL"))
    story.append(P(digest[:32] + " " + digest[32:]))
    story.append(photo(image))

    heading("02 / Embedded metadata")
    fields = list((metadata or {}).items())
    if fields:
        grid([(str(k), str(v)[:280]) for k, v in fields[:100]])
        if len(fields) > 100:
            story.append(P(f"Only the first 100 of {len(fields)} metadata fields are displayed.", "SmallDEL"))
        if any(len(str(v)) > 280 for _, v in fields[:100]):
            story.append(P("Some long metadata values were shortened for layout.", "SmallDEL"))
    else:
        story.append(P("No metadata returned by the existing module."))

    heading("03 / Error Level Analysis")
    story.append(P("ELA compares recompression differences. Bright regions do not establish tampering.", "SmallDEL"))
    story.append(photo(ela))

    heading("04 / Copy-Move matching")
    grid([
        ("ORB keypoints", copy_stats["keypoints"]),
        ("Candidate pairs", copy_stats["candidate_pairs"]),
        ("Consistent pairs", copy_stats["consistent_pairs"]),
        ("Pattern found", "Potential repeated-region pattern" if copy_stats["detected"] else "No strong pattern under current settings"),
    ])
    story.append(photo(copy_image))

    heading("05 / Noise inconsistency")
    grid([
        ("Analyzed blocks", noise_stats["analyzed_tiles"]),
        ("Flagged blocks", noise_stats["flagged_tiles"]),
        ("Median residual", noise_stats["median_residual"] if noise_stats["median_residual"] is not None else "N/A"),
        ("Sufficient suitable data", "Yes" if noise_stats["sufficient_data"] else "No"),
    ])
    story.append(P("Local noise residual heatmap", "SmallDEL"))
    story.append(photo(noise_heatmap))
    story.append(P("Highlighted noise outliers", "SmallDEL"))
    story.append(photo(noise_overlay))

    heading("06 / JPEG compression evidence")
    if jpeg["supported"]:
        grid([
            ("Result", jpeg["status"]),
            ("DCT blocks sampled", jpeg["blocks_analyzed"]),
            ("Quantization tables", jpeg["quant_tables"]),
            ("AC quantization step", jpeg["ac_quant_step"]),
            ("Histogram gap bins", ", ".join(map(str, jpeg["gap_bins"])) or "None"),
        ])
        story.append(Spacer(1, 8))
        story.append(histogram(jpeg))
    else:
        story.append(P(jpeg["reason"]))

    heading("07 / Interpretation and limitations")
    story.append(P(
        "These algorithms provide exploratory visual and statistical indicators, not a "
        "validated probability of authenticity. Recompression, repetitive structures, "
        "lighting, camera processing and resizing can create false positives and negatives. "
        "A missing flag does not establish authenticity."
    ))
    story.append(P(
        "Only the original uploaded file is hashed. Illustrations inside this PDF are "
        "resized copies for presentation. Report generation time is not image capture time."
    ))

    def page_footer(canvas, document):
        canvas.saveState()
        w, _ = A4
        canvas.setStrokeColor(BORDER)
        canvas.line(46, 39, w - 46, 39)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(46, 26, "Results are indicators, not proof.")
        canvas.drawRightString(w - 46, 26, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return buffer.getvalue()
