from pathlib import Path

APP_NAME = "Clarté360 — Émargements"
APP_VERSION = "1.1.0"
BRAND = "#008080"
BRAND_LIGHT = "#F1F8F8"
TEXT = "#1F2937"
MUTED = "#6B7280"
WARNING = "#B7791F"
DANGER = "#B42318"
SUCCESS = "#067647"
ROOT = Path(__file__).resolve().parent
LOGO_PATH = ROOT / "assets" / "logo_clarte360.png"
ICON_PATH = ROOT / "assets" / "site_icon.png"

LEGAL_LINE_1 = "CLARTÉ360 – 60 rue François 1er – 75008 Paris – Tél. : 01 89 48 08 25 – Email : contact@Clarté360.com – Web : www.Clarté360.com"
LEGAL_LINE_2 = "RCS : 102349834 – SIRET : 10234983400014 – NAF : 8559 A – Id CEE : FR88102349834"

CSS = f"""
<style>
:root {{ --c360: {BRAND}; --c360-light: {BRAND_LIGHT}; --c360-text: {TEXT}; }}
.block-container {{max-width: 1180px; padding-top: 1.5rem; padding-bottom: 4rem;}}
.c360-header {{display:flex;align-items:center;gap:18px;padding:10px 0 18px;border-bottom:1px solid #E5E7EB;margin-bottom:20px;}}
.c360-header img {{width:72px;height:72px;object-fit:contain;}}
.c360-title {{font-size:2rem;font-weight:800;color:{BRAND};line-height:1.05;}}
.c360-subtitle {{color:{MUTED};font-size:1rem;margin-top:5px;}}
.c360-card {{background:{BRAND_LIGHT};border-left:5px solid {BRAND};border-radius:12px;padding:16px 18px;margin:10px 0 18px;}}
.c360-card h3 {{margin:0 0 8px;color:{BRAND};}}
.c360-kpi {{background:white;border:1px solid #D9E7E7;border-radius:12px;padding:14px;min-height:96px;box-shadow:0 1px 2px rgba(0,0,0,.03);}}
.c360-kpi .n {{font-size:1.75rem;font-weight:800;color:{BRAND};}}
.c360-kpi .l {{font-size:.9rem;color:{MUTED};}}
.c360-footer {{margin-top:35px;padding-top:16px;border-top:1px solid #E5E7EB;color:{MUTED};font-size:.78rem;text-align:center;line-height:1.45;}}
.c360-ok {{background:#ECFDF3;border-left:5px solid {SUCCESS};padding:12px;border-radius:10px;}}
.c360-warn {{background:#FFFAEB;border-left:5px solid #F79009;padding:12px;border-radius:10px;}}
.c360-danger {{background:#FEF3F2;border-left:5px solid {DANGER};padding:12px;border-radius:10px;}}
div.stButton > button:first-child {{border-radius:10px;border:1px solid {BRAND};color:{BRAND};background:white;min-height:42px;}}
div.stButton > button:first-child:hover {{border-color:{BRAND};color:{BRAND};background:{BRAND_LIGHT};}}
div.stButton > button[kind="primary"] {{background:{BRAND}!important;color:white!important;border:1px solid {BRAND}!important;font-weight:700;}}
div.stButton > button[kind="primary"] * {{color:white!important;}}
div.stDownloadButton > button:first-child {{border-radius:10px;border:1px solid {BRAND};color:{BRAND};background:white;}}
[data-testid="stSidebar"] {{background:{BRAND_LIGHT};}}
[data-testid="stMetricValue"] {{color:{BRAND};}}
@media (max-width: 700px) {{
 .block-container {{padding-left:1rem;padding-right:1rem;padding-top:.8rem;}}
 .c360-header {{align-items:flex-start;}}
 .c360-header img {{width:56px;height:56px;}}
 .c360-title {{font-size:1.55rem;}}
 .c360-subtitle {{font-size:.9rem;}}
 div.stButton > button:first-child {{min-height:48px;}}
}}
</style>
"""
