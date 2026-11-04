"""Classy Doodle x Korean Diary dashboard for Image Forgery Detection System.

Analysis module APIs are intentionally unchanged. Visual controls only adjust previews.
Requires Streamlit with st.popover support (Streamlit 1.31+).
"""
import base64
import hashlib
import html
import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

from modules.ela import analyze_ela
from modules.metadata import extract_metadata
from modules.noise import analyze_noise
from modules.copy_move import detect_copy_move
from modules.double_jpeg import analyze_double_jpeg
from modules.report import generate_pdf_report

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Image Forgery Detection System", page_icon="✧", layout="wide")
st.markdown(
    f"<style>{(ROOT / 'style.css').read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)

MENU = [
    "⌂ Workspace",
    "◈ Analysis Hub",
    "▤ Evidence Vault",
    "▣ Reports",
    "✎ Case Notes",
    "⚙ Preferences",
    "ⓘ Help & About",
]


def doodle(name, css_class="", description=""):
    """Embed bundled vector illustration without external services."""
    filename = ROOT / "assets" / name
    encoded = base64.b64encode(filename.read_bytes()).decode("ascii")
    return (
        f'<img class="{html.escape(css_class, quote=True)}" '
        f'src="data:image/svg+xml;base64,{encoded}" '
        f'alt="{html.escape(description, quote=True)}">'
    )


def tip(name, description):
    label = html.escape(name, quote=True)
    explanation = html.escape(description, quote=True)
    return (
        f'<span class="tip" tabindex="0" aria-label="{label}: {explanation}">'
        f'{label}<span class="tiptext" role="tooltip">{explanation}</span></span>'
    )


def section(label):
    st.markdown(f'<div class="section-title">{label}</div>', unsafe_allow_html=True)


def change_menu(destination):
    st.session_state["menu"] = destination


def verdict_view(label):
    styles = {
        "Not assessed": ("unreviewed", "Not assessed", "This image has not received a reviewer assessment."),
        "Likely Authentic": ("authentic", "Likely Authentic", "Reviewer-selected; authenticity is not guaranteed."),
        "Suspicious": ("suspicious", "Suspicious", "Reviewer-selected; further verification is recommended."),
        "Likely Manipulated": ("manipulated", "Likely Manipulated", "Reviewer-selected; independent confirmation is required."),
    }
    css, title, explanation = styles[label]
    st.markdown(
        f'<div class="verdict {css}"><strong>{title}</strong><p>{explanation}</p></div>',
        unsafe_allow_html=True,
    )


def download_report(image_bytes, filename, image, digest, assessment, suffix):
    """Create a report only on click; prevent stale reports being downloaded."""
    if st.button("✧ Generate PDF Report", key="make_pdf_" + suffix):
        try:
            with st.spinner("Preparing forensic PDF…"):
                pdf = generate_pdf_report(image_bytes, filename, image, assessment)
            st.session_state["pdf_cache"] = pdf
            st.session_state["pdf_key"] = (digest, assessment)
            st.toast("The PDF report is ready.")
        except Exception as exc:
            st.error(f"Report generation failed: {exc}")
    if st.session_state.get("pdf_key") == (digest, assessment) and st.session_state.get("pdf_cache"):
        st.download_button(
            "↓ Download PDF Report",
            data=st.session_state["pdf_cache"],
            file_name=f"forensic_report_{digest[:12]}.pdf",
            mime="application/pdf",
            key="save_pdf_" + suffix,
        )
    else:
        st.caption("Generate a fresh PDF after changing the uploaded image or reviewer verdict.")


# Load and check evidence BEFORE creating the reviewer widget.
uploaded_file = None
image = None
file_bytes = None
digest = None

st.markdown(
    f"""
    <div class="hero">
      <div class="eyebrow">✧ The Evidence Atelier / digital forensics diary</div>
      <div class="hero-title">Image Forgery Detection System</div>
      <p class="hero-subtitle">Analyze · Detect · Verify · Generate Forensic Report</p>
      <span class="hero-asterisk">✷ small details matter</span>
      {doodle('peeking-cat.svg', 'hero-doodle', 'Tiny cat mascot peeking over the page')}
    </div>
    <div class="hero-bottom-note">
      <span class="lead">a little curiosity, a lot of evidence ✦</span>
      <span class="diary-note sage">original evidence stays untouched ♡</span>
    </div>
    """, unsafe_allow_html=True,
)

uploaded_file = st.file_uploader(
    "Upload an image for analysis (JPEG / PNG · maximum 20 MB)",
    type=["jpg", "jpeg", "png"],
)

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    if len(file_bytes) > 20 * 1024 * 1024:
        st.error("Please upload a file under 20 MB.")
        st.stop()
    try:
        image = Image.open(BytesIO(file_bytes))
        if image.width * image.height > 20_000_000:
            st.error("Image exceeds the 20-million-pixel safety limit.")
            st.stop()
        image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        st.error("Unable to open this image safely.")
        st.stop()
    digest = hashlib.sha256(file_bytes).hexdigest()
    if st.session_state.get("current_digest") != digest:
        st.session_state["current_digest"] = digest
        st.session_state["review_verdict"] = "Not assessed"
        st.session_state.pop("pdf_cache", None)
        st.session_state.pop("pdf_key", None)
        st.session_state["case_notes"] = ""

# Permanent, useful sidebar navigation.
with st.sidebar:
    st.markdown(
        f'<div class="sidebar-brand">'
        f'{doodle("guddu.svg", description="Guddu holding a little white cat")}'
        f'<div class="brand-title">The Evidence Atelier</div>'
        f'<div class="brand-note">evidence, but make it lovely ♡</div>'
        f'</div>', unsafe_allow_html=True,
    )
    st.caption("A PRIVATE, LOCAL FORENSIC WORKSPACE")
    st.radio("Main navigation", MENU, key="menu", label_visibility="collapsed")
    st.divider()
    st.markdown("**Reviewer assessment**")
    review = st.selectbox(
        "Verdict",
        ["Not assessed", "Likely Authentic", "Suspicious", "Likely Manipulated"],
        key="review_verdict",
        help="Assigned manually by the examiner; not calculated by the detection modules.",
    )
    with st.expander("⚙ Analysis preview controls"):
        jpeg_quality = st.slider("JPEG quality preview", 50, 100, 90, 5)
        noise_contrast = st.slider("Noise heatmap contrast", 0.75, 2.0, 1.0, 0.05)
        st.caption("Both sliders affect visual previews only. Detection functions remain unchanged.")
    with st.expander("ⓘ Project information"):
        st.write("Version: Classy Doodle × Korean Diary")
        st.caption("Local app · Streamlit · Pillow · OpenCV")
        st.caption("Results are indicators, not proof.")

# Real interactive pop-ups with functional navigation.
a, b, _ = st.columns([1.2, 1.2, 3])
with a:
    with st.popover("✦ Quick actions", use_container_width=True):
        st.markdown('<div class="pop-card"><strong>✎ A little shortcut diary</strong><p>Jump straight to the tool you need.</p></div>', unsafe_allow_html=True)
        st.button("◈ Analysis Hub", key="quick_analysis", use_container_width=True, on_click=change_menu, args=(MENU[1],))
        st.button("▤ Evidence Vault", key="quick_evidence", use_container_width=True, on_click=change_menu, args=(MENU[2],))
        st.button("▣ PDF Reports", key="quick_reports", use_container_width=True, on_click=change_menu, args=(MENU[3],))
with b:
    with st.popover("ⓘ Evidence status", use_container_width=True):
        if image is None:
            st.markdown('<div class="pop-card">No image uploaded yet. Add an image to begin.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="pop-card">Image loaded successfully. SHA-256 calculated from the original bytes.</div>', unsafe_allow_html=True)
            st.code(digest, language=None)
        st.caption("No automatic authenticity conclusion is produced.")

if image is None:
    st.markdown(
        f'<div class="welcome-illustration">'
        f'<span class="diary-note cream">✎ Your image investigation starts here!</span>'
        f'{doodle("stars.svg", description="Black ink stars and hearts")}'
        f'</div>', unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="welcome-wrap">'
        '<div class="welcome-card"><span class="number">01.</span><strong>Upload evidence</strong>'
        '<p>Choose a local JPEG or PNG. We calculate the SHA-256 of its exact bytes.</p></div>'
        '<div class="welcome-card"><span class="number">02.</span><strong>Explore clues</strong>'
        '<p>Compare ELA, metadata, noise, copy-move and JPEG compression indicators.</p></div>'
        '<div class="welcome-card"><span class="number">03.</span><strong>Save your notes</strong>'
        '<p>Export a PDF report and document your review with professional care.</p></div>'
        '</div>', unsafe_allow_html=True,
    )
    st.info("Upload an image above to activate the six forensic tabs and your evidence tools.")

else:
    selected_menu = st.session_state["menu"]

    if selected_menu == MENU[0]:
        # Do not rename or remove these six original tabs.
        tab_overview, tab_ela, tab_metadata, tab_noise, tab_copy, tab_jpeg = st.tabs(
            ["Overview", "ELA", "Metadata", "Noise", "Copy-Move", "Double JPEG"]
        )

        with tab_overview:
            verdict_view(review)
            st.markdown(
                f'<div class="welcome-illustration">'
                f'<span class="diary-note sage">✧ evidence needs a careful second look</span>'
                f'{doodle("doodle-sprig.svg", description="Hand-drawn black flower doodle")}'
                f'</div>', unsafe_allow_html=True,
            )
            m1, m2, m3 = st.columns(3)
            m1.metric("Image width", f"{image.width:,} px")
            m2.metric("Image height", f"{image.height:,} px")
            m3.metric("File size", f"{len(file_bytes) / 1024:,.1f} KB")
            section("Original evidence")
            st.image(ImageOps.exif_transpose(image), width="stretch")
            section(tip("SHA-256 fingerprint", "A fingerprint of the original uploaded bytes. This does not prove an image is authentic."))
            st.markdown(f'<div class="hash-box">{digest}</div>', unsafe_allow_html=True)
            section("Evidence report")
            download_report(file_bytes, uploaded_file.name, image, digest, review, "workspace")

        with tab_ela:
            section(tip("Error Level Analysis (ELA)", "JPEG recompression differences may reveal processing patterns, but are not proof of forgery."))
            st.image(analyze_ela(image), width="stretch")
            with st.expander("View separate JPEG quality preview"):
                stream = BytesIO()
                ImageOps.exif_transpose(image).convert("RGB").save(stream, format="JPEG", quality=jpeg_quality)
                stream.seek(0)
                with Image.open(stream) as preview:
                    st.image(preview, width="stretch")
                st.caption("This comparison is separate from the unchanged ELA detector.")

        with tab_metadata:
            section(tip("Image metadata / EXIF", "Descriptive information that can be absent, edited or removed."))
            st.json({str(k): str(v)[:500] for k, v in extract_metadata(image).items()})

        with tab_noise:
            section(tip("Noise Inconsistency", "Local residual differences may arise from compression, texture or manipulation."))
            heatmap, marked, stats = analyze_noise(image)
            n1, n2, n3 = st.columns(3)
            n1.metric("Analyzed blocks", stats["analyzed_tiles"])
            n2.metric("Unusual blocks", stats["flagged_tiles"])
            n3.metric("Median residual", stats["median_residual"] if stats["median_residual"] is not None else "N/A")
            left, right = st.columns(2)
            with left:
                st.image(ImageEnhance.Contrast(heatmap).enhance(noise_contrast), caption="Residual heatmap · display adjustment only", width="stretch")
            with right:
                st.image(marked, caption="Highlighted regions", width="stretch")
            if not stats["sufficient_data"]:
                st.info("Insufficient suitable blocks for this method.")
            elif stats["flagged_tiles"]:
                st.warning("Unusual residual patterns found. Review manually.")
            else:
                st.info("No strong residual outliers found by this heuristic.")

        with tab_copy:
            section(tip("Copy-Move / ORB", "Looks for duplicated image feature patterns. Natural repetition can produce false positives."))
            marked, stats = detect_copy_move(image)
            c1, c2, c3 = st.columns(3)
            c1.metric("ORB keypoints", stats["keypoints"])
            c2.metric("Candidate pairs", stats["candidate_pairs"])
            c3.metric("Consistent pairs", stats["consistent_pairs"])
            st.image(marked, width="stretch")
            if stats["detected"]:
                st.warning("Potentially repeated regions found; manual confirmation needed.")
            else:
                st.info("No strong copy-move pattern found by this heuristic.")

        with tab_jpeg:
            section(tip("Double JPEG / DCT", "Exploratory compression-coefficient histogram analysis; not a validated fake-image classifier."))
            if image.format != "JPEG":
                st.info("Double JPEG analysis requires an original JPG/JPEG upload.")
            else:
                result = analyze_double_jpeg(file_bytes)
                if not result["supported"]:
                    st.warning(result["reason"])
                else:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("DCT blocks", result["blocks_analyzed"])
                    c2.metric("Quantization tables", result["quant_tables"])
                    c3.metric("AC quantization step", result["ac_quant_step"])
                    st.bar_chart(
                        {"AC bin": [str(k) for k in result["histogram_bins"]], "Blocks": result["histogram_counts"]},
                        x="AC bin", y="Blocks", height=290,
                    )
                    st.caption("Analysis result: " + result["status"])
                    st.write("Histogram gap bins:", result["gap_bins"])
                    st.info("Compression history is not proof of manipulation.")

    elif selected_menu == MENU[1]:
        st.header("◈ Analysis Hub")
        st.caption("Focus on one method at a time. Your six original tabs remain in Workspace.")
        method = st.selectbox("Choose an analysis", ["ELA", "Metadata", "Noise", "Copy-Move", "Double JPEG"])
        if method == "ELA":
            st.image(analyze_ela(image), width="stretch")
        elif method == "Metadata":
            st.json({str(k): str(v)[:500] for k, v in extract_metadata(image).items()})
        elif method == "Noise":
            heatmap, marked, stats = analyze_noise(image)
            st.write("Analysis statistics:", stats)
            left, right = st.columns(2)
            with left:
                st.image(ImageEnhance.Contrast(heatmap).enhance(noise_contrast), width="stretch")
            with right:
                st.image(marked, width="stretch")
        elif method == "Copy-Move":
            marked, stats = detect_copy_move(image)
            st.write("Matching statistics:", stats)
            st.image(marked, width="stretch")
        else:
            if image.format != "JPEG":
                st.info("Upload a JPEG for DCT histogram analysis.")
            else:
                result = analyze_double_jpeg(file_bytes)
                if result["supported"]:
                    st.bar_chart({"AC bin": [str(k) for k in result["histogram_bins"]], "Blocks": result["histogram_counts"]}, x="AC bin", y="Blocks")
                    st.caption(result["status"])
                else:
                    st.warning(result["reason"])

    elif selected_menu == MENU[2]:
        st.header("▤ Evidence Vault")
        st.caption("Local evidence manifest, not a chain-of-custody certification.")
        st.image(ImageOps.exif_transpose(image), width="stretch")
        st.code(digest, language=None)
        record = {
            "original_filename": uploaded_file.name,
            "format": image.format,
            "dimensions": [image.width, image.height],
            "file_size_bytes": len(file_bytes),
            "sha256": digest,
            "exported_utc": datetime.now(timezone.utc).isoformat(),
            "reviewer_selected_verdict": review,
        }
        st.json(record)
        st.download_button("↓ Download evidence manifest (JSON)", data=json.dumps(record, indent=2), file_name=f"manifest_{digest[:12]}.json", mime="application/json")

    elif selected_menu == MENU[3]:
        st.header("▣ Report Studio")
        verdict_view(review)
        st.write("Create a PDF using the existing ELA, Metadata, Noise, Copy-Move and Double JPEG modules.")
        st.info("A report describes indicators; it cannot independently establish authenticity.")
        download_report(file_bytes, uploaded_file.name, image, digest, review, "reports")

    elif selected_menu == MENU[4]:
        st.header("✎ Case Notes")
        st.caption("Notes are stored only in this Streamlit session; download a copy for retention.")
        notes = st.text_area("Investigator notes", key="case_notes", height=220, placeholder="Describe observations and planned verification steps...")
        notes_txt = f"Evidence SHA-256: {digest}\nFile: {uploaded_file.name}\n\nNotes:\n{notes}\n"
        st.download_button("↓ Save notes as TXT", data=notes_txt, file_name=f"case_notes_{digest[:12]}.txt", mime="text/plain")

    elif selected_menu == MENU[5]:
        st.header("⚙ Preferences")
        st.write("Use sidebar sliders for ELA JPEG preview quality and noise heatmap contrast.")
        st.info("Animated backgrounds and pop-ups are CSS-only. Devices requesting reduced motion receive minimal animation.")
        st.write(f"Current JPEG preview quality: **{jpeg_quality}**")
        st.write(f"Current heatmap contrast: **{noise_contrast:.2f}×**")

    else:
        st.header("ⓘ Help & About")
        st.markdown("**What do the modules mean?**")
        for name, explanation in [
            ("ELA", "Compares local JPEG recompression behavior."),
            ("Metadata", "Reads available file and EXIF properties."),
            ("Noise", "Maps local differences in estimated high-frequency residuals."),
            ("Copy-Move", "Searches for repeated feature arrangements."),
            ("Double JPEG", "Inspects exploratory DCT coefficient histograms."),
            ("SHA-256", "Identifies the exact uploaded bytes; does not prove authenticity."),
        ]:
            with st.expander(name):
                st.write(explanation)
        st.warning("Results are indicators, not proof. Interpret each test in the context of the original evidence.")

st.markdown('<div class="footer">✳ THE EVIDENCE ATELIER ✳ &nbsp; Results are indicators, not proof. &nbsp; ♡</div>', unsafe_allow_html=True)
