CLASSY DOODLE x KOREAN DIARY FORENSICS
====================================

INSTALL (inside Kali Linux)
1. Download classy_doodle_korean_diary.zip IN KALI FIREFOX, not Windows.
2. In Kali terminal:

   cd ~/image-forgery-detection
   source venv/bin/activate
   cp app.py app_before_diary.py
   cp style.css style_before_diary.css
   cp .streamlit/config.toml .streamlit/config_before_diary.toml
   unzip -o ~/Downloads/classy_doodle_korean_diary.zip -d ~/image-forgery-detection
   python -m py_compile app.py
   streamlit run app.py

3. Open http://localhost:8501

If Streamlit already runs, stop it with Ctrl+C before the last command.

IMPORTANT
- Archive overwrites app.py, style.css, and .streamlit/config.toml.
- Archive DOES NOT overwrite any files in modules/.
- Existing modules expected:
  modules/ela.py, metadata.py, noise.py, copy_move.py,
  double_jpeg.py, report.py.
- PDF generation also requires your existing reportlab installation.
- Six original tabs retained: Overview, ELA, Metadata, Noise,
  Copy-Move, Double JPEG.
- Sidebar has seven functional views and two real popovers.
- Human-selected verdicts are NOT automatic authenticity judgments.
- ELA quality and noise contrast sliders alter previews only.
- SHA-256 always hashes original uploaded file bytes.
- CSS animations respect reduced-motion system preferences.
- Doodle SVG graphics are local and need no outside services.
- Google Fonts need internet; local fonts are used if offline.

Customize colors in style.css :root variables. Streamlit's native base
colors are also listed in .streamlit/config.toml.
