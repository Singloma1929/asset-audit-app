import os
import re
import html
import json
import hmac
import hashlib
from io import BytesIO
from datetime import datetime, timedelta, timezone

import pandas as pd
import qrcode
from PIL import Image, ImageDraw, ImageFont
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client, Client

# =========================================================
# --- ⚙️ 1. ตั้งค่าหน้าเว็บ (ต้องอยู่บนสุดเสมอ) ---
# =========================================================
st.set_page_config(
    page_title="ระบบตรวจครุภัณฑ์ (Secure Cloud)",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

THAI_TZ = timezone(timedelta(hours=7))
HEADER_ROW_DEFAULT = 4

M_SEARCH = "🔍 ค้นหา / แก้ไข"
M_AUDIT = "📷 ตรวจนับ / บันทึก"
M_QR = "🏷️ สร้าง QR Code"
M_EXPORT = "📥 ส่งออก Excel"

CONDITION_OPTIONS = [
    "ปกติ",
    "ชำรุด/เสียหาย",
    "หมดความจำเป็น",
    "ให้ยืม/ยืมมา",
    "โอน",
    "แลกเปลี่ยน",
    "เสื่อมสภาพ",
    "สูญหาย",
    "รอจำหน่าย",
    "จำหน่ายแล้ว",
    "แปรสภาพหรือทำลาย",
]
STATUS_OPTIONS = ["ตรวจแล้ว", "ยังไม่ตรวจ"]
AUDIT_COLS = [
    "สภาพครุภัณฑ์",
    "สถานะการตรวจ",
    "หมายเหตุ",
    "ผู้ตรวจ",
    "วันเดือนปี เวลา ที่ทำการตรวจสอบ",
]

# =========================================================
# --- 🔐 2. จัดการ Secrets & เชื่อมต่อ Supabase Cloud ---
# =========================================================
def get_secret(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return os.getenv(key, default).strip()

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
APP_BASE_URL = get_secret(
    "APP_BASE_URL",
    "https://asset-audit-app-bbywyvjvpavzrkh8skqrmf.streamlit.app/"
).rstrip("/") + "/"

DEFAULT_ADMIN_CODE = get_secret("DEFAULT_ADMIN_CODE").lower()
DEFAULT_ADMIN_PASSWORD = get_secret("DEFAULT_ADMIN_PASSWORD")
DEFAULT_ADMIN_NAME = get_secret("DEFAULT_ADMIN_NAME", "สำนักงานคลังจังหวัดอุทัยธานี")

@st.cache_resource
def init_supabase() -> Client | None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        return None

supabase: Client | None = init_supabase()

# =========================================================
# --- 🎨 3. Responsive CSS (Mobile-First + Desktop) ---
# =========================================================
st.markdown("""
    <style>
    .block-container {
        padding-top: 2.5rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 1280px;
    }
    .app-header {
        font-size: clamp(20px, 4vw, 28px);
        font-weight: 700;
        color: #1f2937;
        margin-top: 4px;
        margin-bottom: 10px;
        line-height: 1.35 !important;
    }
    .agency-banner {
        background: linear-gradient(135deg, #1e3a8a, #2563eb);
        color: #ffffff;
        padding: 10px 14px;
        border-radius: 10px;
        font-weight: 600;
        font-size: 14px;
        margin-bottom: 12px;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        justify-content: space-between;
        align-items: center;
    }
    .agency-pill {
        font-size: 12px;
        background: rgba(255,255,255,0.22);
        padding: 3px 10px;
        border-radius: 999px;
        white-space: nowrap;
    }

    /* 📊 Responsive Metric Grid (มือถือ 2 คอลัมน์ / จอใหญ่ 6 คอลัมน์) */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 8px;
        margin-bottom: 6px;
    }
    @media (max-width: 900px) {
        .kpi-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
    }
    @media (max-width: 520px) {
        .kpi-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }
    .kpi-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 10px 12px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        min-height: 76px;
    }
    .kpi-label {
        font-size: 12px;
        color: #475569;
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .kpi-val {
        font-size: 22px;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.25;
        margin-top: 2px;
    }
    .kpi-green { border-left: 4px solid #16a34a; }
    .kpi-amber { border-left: 4px solid #f59e0b; }
    .kpi-red   { border-left: 4px solid #dc2626; }
    .kpi-blue  { border-left: 4px solid #2563eb; }

    /* Progress Bar */
    .progress-wrapper {
        background-color: #e5e7eb;
        border-radius: 999px;
        width: 100%;
        height: 18px;
        overflow: hidden;
        margin-top: 6px;
        margin-bottom: 12px;
        box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
    }
    .progress-fill {
        background: linear-gradient(90deg, #22c55e, #16a34a);
        height: 100%;
        border-radius: 999px;
        transition: width 0.35s ease;
    }

    /* Status Badges */
    .status-box-green {
        background-color: #dcfce7;
        color: #166534;
        border: 1px solid #86efac;
        padding: 10px 14px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 14px;
        display: flex;
        align-items: center;
        min-height: 44px;
    }
    .status-box-red {
        background-color: #fee2e2;
        color: #991b1b;
        border: 1px solid #fca5a5;
        padding: 10px 14px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 14px;
        display: flex;
        align-items: center;
        min-height: 44px;
    }

    /* 🟢 ปุ่มเมนูนำทาง st.radio ให้แตะง่ายและตัดบรรทัดสวยบนมือถือ */
    [data-testid="stRadio"] > div[role="radiogroup"] {
        background-color: #f8fafc;
        padding: 8px 12px;
        border-radius: 12px;
        border: 1px solid #cbd5e1;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        justify-content: space-around;
    }
    [data-testid="stRadio"] div[role="radiogroup"] label {
        padding: 6px 10px;
        border-radius: 8px;
        margin: 0 !important;
        min-height: 40px;
        display: flex;
        align-items: center;
    }
    [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p {
        color: #15803d !important;
        font-weight: 800 !important;
    }

    /* ปุ่มกดให้แตะง่ายด้วยนิ้วโป้งบนมือถือ */
    button[kind="primary"], button[kind="secondary"] {
        min-height: 44px !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }

    /* 💬 Popup แจ้งเตือนชั่วคราว */
    @keyframes popupFadeOut {
        0% { opacity: 1; transform: translate(-50%, -50%) scale(0.95); }
        15% { opacity: 1; transform: translate(-50%, -50%) scale(1.02); }
        75% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
        100% { opacity: 0; transform: translate(-50%, -50%) scale(0.95); visibility: hidden; }
    }
    .auto-popup-badge {
        position: fixed;
        top: 30%;
        left: 50%;
        transform: translate(-50%, -50%);
        z-index: 999999;
        padding: 16px 26px;
        border-radius: 12px;
        font-size: 18px;
        font-weight: 700;
        color: #ffffff;
        box-shadow: 0 10px 25px rgba(0,0,0,0.25);
        pointer-events: none;
        animation: popupFadeOut 1.3s ease-in-out forwards;
        text-align: center;
        max-width: 90vw;
    }
    .popup-success {
        background-color: rgba(22, 163, 74, 0.96);
        border: 2px solid #bbf7d0;
    }
    .popup-error {
        background-color: rgba(220, 38, 38, 0.96);
        border: 2px solid #fecaca;
    }
    </style>
""", unsafe_allow_html=True)

# =========================================================
# --- 🛠️ 4. ฟังก์ชันความปลอดภัยและยูทิลิตี้ ---
# =========================================================
def now_thai() -> datetime:
    return datetime.now(THAI_TZ)

def safe_compare(a: str, b: str) -> bool:
    """เปรียบเทียบข้อความแบบปลอดภัย รองรับทั้งภาษาอังกฤษและ UTF-8/ภาษาไทย"""
    return hmac.compare_digest(str(a).encode("utf-8"), str(b).encode("utf-8"))

def hash_password(plain_password: str) -> str:
    """เข้ารหัสรหัสผ่านด้วย PBKDF2-HMAC-SHA256"""
    iterations = 120_000
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"

def verify_password(plain_password: str, stored_password: str) -> tuple[bool, bool]:
    """คืนค่า (รหัสผ่านถูกต้องหรือไม่, ต้องอัปเกรดเป็น Hash หรือไม่)"""
    stored = str(stored_password or "").strip()
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iter_str, salt_hex, hash_hex = stored.split("$", 3)
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iter_str),
            )
            return safe_compare(dk.hex(), hash_hex), False
        except Exception:
            return False, False
    is_match = safe_compare(plain_password, stored)
    return is_match, is_match

def authenticate_agency(agency_code: str, password: str) -> tuple[bool, str, str]:
    """ตรวจสอบสิทธิ์หน่วยงานและอัปเกรดรหัสผ่านเดิมเป็น Hash อัตโนมัติ"""
    code_in = str(agency_code or "").strip().lower()
    pass_in = str(password or "").strip()

    if not code_in or not pass_in:
        return False, "", "⚠️ กรุณากรอกรหัสหน่วยงานและรหัสผ่านให้ครบถ้วน"

    if DEFAULT_ADMIN_CODE and DEFAULT_ADMIN_PASSWORD:
        if code_in == DEFAULT_ADMIN_CODE and safe_compare(pass_in, DEFAULT_ADMIN_PASSWORD):
            return True, DEFAULT_ADMIN_NAME, ""

    if not supabase:
        return False, "", "⚠️ ไม่สามารถเชื่อมต่อฐานข้อมูลได้ กรุณาตรวจสอบค่า SUPABASE_URL และ SUPABASE_KEY ใน Secrets"

    try:
        res = (
            supabase.table("agencies")
            .select("agency_code, agency_name, password")
            .eq("agency_code", code_in)
            .limit(1)
            .execute()
        )
        if not res.data:
            return False, "", "❌ ไม่พบรหัสหน่วยงานนี้ในระบบ หรือรหัสผ่านไม่ถูกต้อง"

        matched = res.data[0]
        is_valid, needs_upgrade = verify_password(pass_in, matched.get("password", ""))
        if not is_valid:
            return False, "", "❌ รหัสผ่านไม่ถูกต้อง"

        if needs_upgrade:
            try:
                supabase.table("agencies").update(
                    {"password": hash_password(pass_in)}
                ).eq("agency_code", code_in).execute()
            except Exception:
                pass

        return True, str(matched.get("agency_name") or code_in), ""
    except Exception as e:
        return False, "", f"⚠️ ข้อผิดพลาดเชื่อมต่อฐานข้อมูล: {e}"

def change_agency_password(agency_code: str, old_password: str, new_password: str) -> tuple[bool, str]:
    """ตรวจสอบรหัสผ่านเดิมและบันทึกรหัสผ่านใหม่แบบเข้ารหัสลง Supabase"""
    code_in = str(agency_code or "").strip().lower()
    old_in = str(old_password or "").strip()
    new_in = str(new_password or "").strip()

    if DEFAULT_ADMIN_CODE and DEFAULT_ADMIN_PASSWORD and code_in == DEFAULT_ADMIN_CODE:
        return False, "⚠️ บัญชีผู้ดูแลหลักนี้ผูกกับ Streamlit Secrets กรุณาเปลี่ยนรหัสผ่านที่เมนู App settings > Secrets"

    if not old_in or not new_in:
        return False, "⚠️ กรุณากรอกรหัสผ่านเดิมและรหัสผ่านใหม่ให้ครบถ้วน"
    if len(new_in) < 6:
        return False, "⚠️ รหัสผ่านใหม่ต้องมีความยาวอย่างน้อย 6 ตัวอักษร"
    if old_in == new_in:
        return False, "⚠️ รหัสผ่านใหม่ต้องไม่ซ้ำกับรหัสผ่านเดิม"
    if not supabase:
        return False, "⚠️ ไม่ได้เชื่อมต่อฐานข้อมูล Supabase"

    try:
        res = (
            supabase.table("agencies")
            .select("password")
            .eq("agency_code", code_in)
            .limit(1)
            .execute()
        )
        if not res.data:
            return False, "❌ ไม่พบข้อมูลหน่วยงานในฐานข้อมูล"

        is_valid, _ = verify_password(old_in, res.data[0].get("password", ""))
        if not is_valid:
            return False, "❌ รหัสผ่านเดิมไม่ถูกต้อง"

        supabase.table("agencies").update(
            {"password": hash_password(new_in)}
        ).eq("agency_code", code_in).execute()
        return True, "✅ เปลี่ยนรหัสผ่านสำเร็จเรียบร้อย! (ใช้รหัสผ่านใหม่ในการเข้าสู่ระบบครั้งถัดไป)"
    except Exception as e:
        return False, f"⚠️ เกิดข้อผิดพลาดในการเปลี่ยนรหัสผ่าน: {e}"

def show_1sec_popup(message: str, is_success: bool = True):
    cls = "popup-success" if is_success else "popup-error"
    safe_msg = html.escape(message)
    st.markdown(f"<div class='auto-popup-badge {cls}'>{safe_msg}</div>", unsafe_allow_html=True)

def is_valid_asset_code(val) -> bool:
    if pd.isna(val):
        return False
    val_str = str(val).strip()
    if val_str == "" or val_str.lower() in {"nan", "none"} or val_str == "-":
        return False
    return bool(re.search(r"\d", val_str))

def extract_scan_code(raw_val: str) -> str:
    val = str(raw_val or "").strip()
    if "?scan=" in val:
        val = val.split("?scan=").pop().split("&")[0].strip()
    return val

def find_asset_code_column(columns) -> str:
    cols = [str(c) for c in columns]
    priority_keywords = ["หมายเลขครุภัณฑ์", "รหัสครุภัณฑ์", "เลขครุภัณฑ์", "รหัส", "เลข"]
    for kw in priority_keywords:
        for c in cols:
            if kw in c:
                return c
    return cols[0] if cols else "หมายเลขครุภัณฑ์"

def parse_excel_dataframe(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """ตัวอ่านไฟล์ Excel มาตรฐานเดียว รองรับทั้งหัวตาราง 1 ชั้น และ 2 ชั้น"""
    header_idx = None
    scan_limit = min(15, len(raw_df))
    for idx in range(scan_limit):
        row_vals = [str(v).strip() for v in raw_df.iloc[idx].values if pd.notna(v)]
        if any(any(k in val for k in ["หมายเลขครุภัณฑ์", "รหัสครุภัณฑ์", "เลขครุภัณฑ์"]) for val in row_vals):
            header_idx = idx
            break
        if any("รายการ" in val for val in row_vals) and any(("รหัส" in val or "เลข" in val) for val in row_vals):
            header_idx = idx
            break

    if header_idx is None:
        header_idx = HEADER_ROW_DEFAULT if len(raw_df) > HEADER_ROW_DEFAULT else 0

    top_cols = raw_df.iloc[header_idx].fillna("").astype(str).str.strip().tolist()
    has_sub_header = False

    if header_idx + 1 < len(raw_df):
        next_row = raw_df.iloc[header_idx + 1].fillna("").astype(str).str.strip().tolist()
        tentative_code_idx = next(
            (i for i, c in enumerate(top_cols) if any(k in c for k in ["หมายเลขครุภัณฑ์", "รหัส", "เลข"])),
            0,
        )
        next_code_val = next_row[tentative_code_idx] if tentative_code_idx < len(next_row) else ""
        non_empty_next = [v for v in next_row if v and v not in {"None", "nan"}]
        if non_empty_next and not is_valid_asset_code(next_code_val):
            has_sub_header = True

    if has_sub_header:
        sub_cols = raw_df.iloc[header_idx + 1].fillna("").astype(str).str.strip().tolist()
        combined_columns = []
        for idx, (t, s) in enumerate(zip(top_cols, sub_cols)):
            t_clean = "" if t in {"None", "nan"} else t
            s_clean = "" if s in {"None", "nan"} else s
            if s_clean and s_clean != t_clean:
                combined_columns.append(f"{t_clean} ({s_clean})" if t_clean else s_clean)
            else:
                combined_columns.append(t_clean if t_clean else f"Unnamed_{idx}")
        data_start = header_idx + 2
    else:
        combined_columns = [
            c if c and c not in {"None", "nan"} else f"Unnamed_{i}"
            for i, c in enumerate(top_cols)
        ]
        data_start = header_idx + 1

    seen = {}
    unique_cols = []
    for c in combined_columns:
        if c in seen:
            seen[c] += 1
            unique_cols.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            unique_cols.append(c)

    df = raw_df.iloc[data_start:].copy()
    df.columns = unique_cols
    df = df.dropna(how="all").reset_index(drop=True)
    target_col = find_asset_code_column(df.columns)
    return df, target_col

def read_excel_source(source) -> pd.DataFrame:
    if isinstance(source, str) and source.lower().endswith(".csv"):
        return pd.read_csv(source, header=None)
    try:
        return pd.read_excel(source, header=None, engine="openpyxl")
    except Exception:
        return pd.read_excel(source, header=None, engine="xlrd")

# =========================================================
# --- ☁️ 5. ฟังก์ชันจัดการข้อมูล Supabase (รองรับ >1,000 แถว) ---
# =========================================================
def fetch_all_rows(
    table_name: str,
    select_cols: str = "*",
    filters: dict | None = None,
    order_col: str | None = None,
    page_size: int = 1000,
) -> list[dict]:
    """ดึงข้อมูลครบทุกแถวแบบ Pagination แก้ข้อจำกัด 1,000 แถวของ Supabase"""
    if not supabase:
        return []
    all_rows = []
    offset = 0
    while True:
        query = supabase.table(table_name).select(select_cols)
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        if order_col:
            query = query.order(order_col)
        res = query.range(offset, offset + page_size - 1).execute()
        batch = res.data or []
        all_rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return all_rows

@st.cache_data(ttl=30, show_spinner=False)
def get_agency_years(agency_id: str) -> list[str]:
    years_set = set()
    if agency_id in {"cgduthai", "default_agency"}:
        years_set.update(["2570", "2569", "2568"])

    if supabase:
        for tbl, order_c in [("agency_assets", "fiscal_year"), ("core_assetauditrecord", "id")]:
            try:
                rows = fetch_all_rows(tbl, "fiscal_year", {"agency_id": agency_id}, order_col=order_c)
                for r in rows:
                    fy = str(r.get("fiscal_year") or "").strip()
                    if fy and fy != "รอการอัปโหลดไฟล์":
                        years_set.add(fy)
            except Exception:
                pass

    return sorted(years_set, reverse=True) if years_set else ["รอการอัปโหลดไฟล์"]

@st.cache_data(ttl=60, show_spinner=False)
def get_shared_data(fiscal_year_str: str, agency_id: str) -> tuple[pd.DataFrame, str, str]:
    target_col = "หมายเลขครุภัณฑ์"
    default_columns = [target_col, "รายการ", "อยู่ที่"] + AUDIT_COLS

    if fiscal_year_str == "รอการอัปโหลดไฟล์":
        return pd.DataFrame(columns=default_columns), target_col, "รอการอัปโหลดไฟล์"

    year_key = str(fiscal_year_str).strip()
    for known_y in ("2568", "2569", "2570"):
        if known_y in year_key:
            year_key = known_y
            break

    df = None

    if supabase:
        try:
            asset_rows = fetch_all_rows(
                "agency_assets",
                "asset_code, row_data",
                {"agency_id": agency_id, "fiscal_year": year_key},
                order_col="asset_code",
            )
            if asset_rows:
                parsed_rows = [
                    item["row_data"]
                    for item in asset_rows
                    if isinstance(item.get("row_data"), dict)
                ]
                if parsed_rows:
                    df = pd.DataFrame(parsed_rows)
                    target_col = find_asset_code_column(df.columns)
        except Exception:
            df = None

    if df is None:
        if agency_id in {"cgduthai", "default_agency"}:
            if year_key in {"2568", "2569"}:
                file_candidates = [f"default_asset_{year_key}.xlsx", f"default_asset_{year_key}.xls"]
            else:
                file_candidates = [
                    f"default_asset_{year_key}.xlsx",
                    "default_asset.xlsx",
                    "default_asset.xls",
                    "default_asset_2570.xlsx",
                ]
            default_file = next((f for f in file_candidates if os.path.exists(f)), None)
            if default_file:
                raw_local = read_excel_source(default_file)
                df, target_col = parse_excel_dataframe(raw_local)
            else:
                df = pd.DataFrame(columns=default_columns)
        else:
            df = pd.DataFrame(columns=default_columns)

    for col in AUDIT_COLS:
        if col not in df.columns:
            df[col] = "ยังไม่ตรวจ" if col == "สถานะการตรวจ" else "-"

    if target_col not in df.columns:
        df[target_col] = "-"

    df = df.fillna("-").astype(str).replace({"nan": "-", "None": "-", "": "-"})

    if supabase:
        try:
            saved_data = fetch_all_rows(
                "core_assetauditrecord",
                "*",
                {"fiscal_year": year_key, "agency_id": agency_id},
                order_col="id",
            )
            if saved_data:
                audit_map = {}
                for row in saved_data:
                    code = str(row.get("asset_code") or "").strip()
                    if not code:
                        continue
                    raw_note = str(row.get("note") or "-")
                    actual_note = raw_note
                    extra_info = {}
                    if "||ASSET_DATA||" in raw_note:
                        parts = raw_note.split("||ASSET_DATA||", 1)
                        actual_note = parts[0].strip() if parts[0].strip() else "-"
                        try:
                            extra_info = json.loads(parts[1])
                        except Exception:
                            extra_info = {}

                    audit_map[code] = {
                        "condition": str(row.get("condition") or "-"),
                        "status": str(row.get("status") or "ยังไม่ตรวจ"),
                        "inspector": str(row.get("inspector") or "-"),
                        "updated_at": str(row.get("updated_at") or "-"),
                        "actual_note": actual_note,
                        "extra_info": extra_info,
                    }

                all_columns = list(df.columns)
                records = df.to_dict("records")
                matched_codes = set()

                for rec in records:
                    code = str(rec.get(target_col, "")).strip()
                    audit = audit_map.get(code)
                    if not audit:
                        continue
                    matched_codes.add(code)
                    rec["สภาพครุภัณฑ์"] = audit["condition"]
                    rec["สถานะการตรวจ"] = audit["status"]
                    rec["ผู้ตรวจ"] = audit["inspector"]
                    rec["วันเดือนปี เวลา ที่ทำการตรวจสอบ"] = audit["updated_at"]

                    extra = audit["extra_info"]
                    if audit["actual_note"] not in {"-", ""}:
                        rec["หมายเหตุ"] = audit["actual_note"]
                    elif "หมายเหตุ_ข้อมูลหลัก" in extra:
                        rec["หมายเหตุ"] = str(extra["หมายเหตุ_ข้อมูลหลัก"])

                    for col_k, val_v in extra.items():
                        if col_k in all_columns and col_k != "หมายเหตุ_ข้อมูลหลัก":
                            rec[col_k] = str(val_v)

                for code, audit in audit_map.items():
                    if code in matched_codes:
                        continue
                    extra = audit["extra_info"]
                    new_rec = {c: "-" for c in all_columns}
                    new_rec[target_col] = code
                    new_rec["สภาพครุภัณฑ์"] = audit["condition"]
                    new_rec["สถานะการตรวจ"] = audit["status"]
                    new_rec["หมายเหตุ"] = (
                        audit["actual_note"]
                        if audit["actual_note"] not in {"-", ""}
                        else str(extra.get("หมายเหตุ_ข้อมูลหลัก", "-"))
                    )
                    new_rec["ผู้ตรวจ"] = audit["inspector"]
                    new_rec["วันเดือนปี เวลา ที่ทำการตรวจสอบ"] = audit["updated_at"]
                    for col_k, val_v in extra.items():
                        if col_k in all_columns and col_k != "หมายเหตุ_ข้อมูลหลัก":
                            new_rec[col_k] = str(val_v)
                    records.append(new_rec)

                df = pd.DataFrame(records, columns=all_columns)
        except Exception as e:
            st.error(f"⚠️ เกิดข้อผิดพลาดในการโหลดข้อมูลจาก Supabase: {e}")

    return df, target_col, year_key

def save_progress_to_supabase(
    asset_code: str,
    condition: str,
    status: str,
    note: str,
    inspector: str,
    timestamp: str,
    fiscal_year: str,
    agency_id: str,
    extra_dict: dict | None = None,
) -> bool:
    if not supabase:
        st.error("⚠️ ไม่ได้เชื่อมต่อกับ Supabase Cloud")
        return False
    try:
        clean_code = str(asset_code).strip()
        existing = (
            supabase.table("core_assetauditrecord")
            .select("id, note")
            .eq("asset_code", clean_code)
            .eq("fiscal_year", fiscal_year)
            .eq("agency_id", agency_id)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )

        saved_extra = {}
        record_id = None
        if existing.data:
            record_id = existing.data[0].get("id")
            old_note = str(existing.data[0].get("note") or "")
            if "||ASSET_DATA||" in old_note:
                try:
                    saved_extra = json.loads(old_note.split("||ASSET_DATA||", 1)[1])
                except Exception:
                    saved_extra = {}

        clean_note = str(note).split("||ASSET_DATA||")[0].strip() or "-"
        if extra_dict is not None:
            saved_extra.update(extra_dict)
        saved_extra["หมายเหตุ_ข้อมูลหลัก"] = clean_note

        final_note = (
            f"{clean_note}||ASSET_DATA||{json.dumps(saved_extra, ensure_ascii=False)}"
            if saved_extra
            else clean_note
        )

        payload = {
            "asset_code": clean_code,
            "condition": condition,
            "status": status,
            "note": final_note,
            "inspector": inspector,
            "updated_at": timestamp,
            "fiscal_year": fiscal_year,
            "agency_id": agency_id,
        }

        if record_id:
            supabase.table("core_assetauditrecord").update(payload).eq("id", record_id).execute()
        else:
            supabase.table("core_assetauditrecord").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"⚠️ ไม่สามารถบันทึกลง Supabase ได้: {e}")
        return False

def delete_asset_from_supabase(asset_code: str, fiscal_year: str, agency_id: str) -> bool:
    if not supabase:
        st.error("⚠️ ไม่ได้เชื่อมต่อกับ Supabase Cloud")
        return False
    try:
        clean_code = str(asset_code).strip()
        supabase.table("core_assetauditrecord").delete().eq("asset_code", clean_code).eq("fiscal_year", fiscal_year).eq("agency_id", agency_id).execute()
        supabase.table("agency_assets").delete().eq("asset_code", clean_code).eq("fiscal_year", fiscal_year).eq("agency_id", agency_id).execute()
        return True
    except Exception as e:
        st.error(f"⚠️ ไม่สามารถลบข้อมูลจาก Supabase ได้: {e}")
        return False

@st.cache_data(ttl=120, show_spinner=False)
def df_to_excel_bytes(export_df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    export_df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()

@st.cache_data(ttl=300, show_spinner=False)
def generate_qr_label_png(asset_code: str, base_url: str) -> bytes:
    qr_payload = f"{base_url}?scan={asset_code}"
    qr = qrcode.QRCode(version=1, box_size=12, border=2)
    qr.add_data(qr_payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_w, qr_h = qr_img.size

    text = str(asset_code).strip()
    font = None
    for font_name in ("arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(font_name, 22)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    temp_draw = ImageDraw.Draw(qr_img)
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    canvas_w = max(qr_w, text_w + 28)
    canvas_h = qr_h + text_h + 24

    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    canvas.paste(qr_img, ((canvas_w - qr_w) // 2, 0))

    draw = ImageDraw.Draw(canvas)
    draw.text(((canvas_w - text_w) // 2, qr_h + 4), text, fill="black", font=font)

    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()

def render_status_badge(status_val: str, cond_val: str, inspector_val: str):
    if status_val == "ตรวจแล้ว":
        detail = (
            f" (สภาพ: {html.escape(cond_val)} | ผู้ตรวจ: {html.escape(inspector_val)})"
            if cond_val != "-"
            else ""
        )
        st.markdown(
            f"<div class='status-box-green'>✅ ผ่านการตรวจแล้ว{detail}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div class='status-box-red'>❌ ยังไม่ได้ตรวจ</div>", unsafe_allow_html=True)

def render_save_status_badge(status_val: str, timestamp_val: str):
    if status_val == "ตรวจแล้ว":
        t_info = f" (เมื่อ: {html.escape(timestamp_val)})" if timestamp_val and timestamp_val != "-" else ""
        st.markdown(
            f"<div class='status-box-green'>✅ บันทึกแล้ว{t_info}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("<div class='status-box-red'>❌ รายการนี้ยังไม่ได้บันทึก</div>", unsafe_allow_html=True)

def render_auto_submit_qr_scanner():
    scanner_html = """
    <div style="background: #f8fafc; padding: 10px; border-radius: 10px; border: 1px solid #cbd5e1; text-align: center;">
        <div id="qr-reader" style="width: 100%; max-width: 360px; margin: 0 auto;"></div>
        <div id="qr-result" style="margin-top: 8px; font-family: sans-serif; font-size: 14px; color: #16a34a; font-weight: 700;">
            📷 กำลังเปิดกล้อง... ส่องไปที่ป้าย QR Code
        </div>
    </div>
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
    <script>
        const html5QrCode = new Html5Qrcode("qr-reader");
        const qrConfig = { fps: 15, qrbox: { width: 220, height: 220 }, aspectRatio: 1.0 };
        let isSubmitted = false;

        html5QrCode.start(
            { facingMode: "environment" },
            qrConfig,
            (decodedText) => {
                if (isSubmitted) return;
                isSubmitted = true;
                if (navigator.vibrate) navigator.vibrate(100);

                let rawData = decodedText.trim();
                let assetCode = rawData.includes("?scan=")
                    ? rawData.split("?scan=").pop().split("&")[0].trim()
                    : rawData;

                const statusEl = document.getElementById("qr-result");
                statusEl.textContent = "🔄 กำลังดึงข้อมูลรหัส: " + assetCode + "...";

                html5QrCode.stop().finally(() => {
                    const parentDoc = window.parent.document;
                    const targetInput = parentDoc.querySelector('input[aria-label="กรอกหมายเลขครุภัณฑ์ เพื่อค้นหา"]');
                    if (targetInput) {
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                        setter.call(targetInput, assetCode);
                        targetInput.dispatchEvent(new Event("input", { bubbles: true }));
                        targetInput.dispatchEvent(new Event("change", { bubbles: true }));
                        targetInput.focus();

                        setTimeout(() => {
                            targetInput.dispatchEvent(new KeyboardEvent("keydown", {
                                bubbles: true, cancelable: true, keyCode: 13, key: "Enter", code: "Enter"
                            }));
                            const buttons = parentDoc.querySelectorAll("button");
                            for (const btn of buttons) {
                                if (btn.innerText && btn.innerText.includes("ค้นหา")) {
                                    btn.click();
                                    break;
                                }
                            }
                        }, 140);
                    }
                });
            },
            () => {}
        ).catch(() => {
            const statusEl = document.getElementById("qr-result");
            statusEl.style.color = "#dc2626";
            statusEl.textContent = "⚠️ ไม่สามารถเปิดกล้องได้ (โปรดอนุญาตสิทธิ์กล้องในเบราว์เซอร์)";
        });
    </script>
    """
    return components.html(scanner_html, height=340)

# =========================================================
# --- 🔐 6. ระบบ Login & ลงทะเบียนหน่วยงาน ---
# =========================================================
if not supabase and not (DEFAULT_ADMIN_CODE and DEFAULT_ADMIN_PASSWORD):
    st.error("⚠️ ยังไม่ได้ตั้งค่าการเชื่อมต่อฐานข้อมูล (`SUPABASE_URL` และ `SUPABASE_KEY` ใน Streamlit Secrets)")
    st.stop()

if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False

if not st.session_state.is_logged_in:
    col_l1, col_l2, col_l3 = st.columns([1, 1.8, 1])
    with col_l2:
        st.markdown(
            "<div style='text-align: center; margin-top: 24px;'>"
            "<h2 style='color: #1e3a8a; margin-bottom: 4px;'>🏛️ เข้าสู่ระบบตรวจครุภัณฑ์</h2>"
            "<p style='color: #64748b;'>Asset Audit Cloud Version</p></div>",
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            with st.form("login_form"):
                login_code = st.text_input("👤 รหัสหน่วยงาน (Agency Code)", placeholder="เช่น cgduthai หรือ school01")
                login_pass = st.text_input("🔑 รหัสผ่าน (Password)", type="password")
                submit_login = st.form_submit_button("🚀 เข้าสู่ระบบ", type="primary", use_container_width=True)

                if submit_login:
                    ok, agency_name, err_msg = authenticate_agency(login_code, login_pass)
                    if ok:
                        st.session_state.is_logged_in = True
                        st.session_state.current_agency = login_code.strip().lower()
                        st.session_state.current_agency_name = agency_name
                        st.rerun()
                    else:
                        st.error(err_msg)

        st.markdown("<hr style='margin: 16px 0px;'>", unsafe_allow_html=True)
        with st.expander("➕ ยังไม่มีหน่วยงาน? คลิกที่นี่เพื่อลงทะเบียน"):
            with st.form("register_agency_form_public"):
                new_code = st.text_input("รหัสหน่วยงาน (a-z, 0-9, _ หรือ - เช่น school01)")
                new_name = st.text_input("ชื่อหน่วยงานเต็ม")
                new_email = st.text_input("อีเมลผู้ดูแลระบบ")
                new_pass = st.text_input("กำหนดรหัสผ่าน (อย่างน้อย 6 ตัวอักษร)", type="password")
                reg_btn = st.form_submit_button("ลงทะเบียนหน่วยงานใหม่", use_container_width=True)

                if reg_btn:
                    clean_code = new_code.strip().lower()
                    clean_name = new_name.strip()
                    clean_pass = new_pass.strip()

                    if not re.match(r"^[a-z0-9_-]{3,32}$", clean_code):
                        st.error("⚠️ รหัสหน่วยงานต้องเป็นภาษาอังกฤษตัวพิมพ์เล็ก ตัวเลข หรือ _/- ความยาว 3-32 ตัวอักษร")
                    elif not clean_name:
                        st.error("⚠️ กรุณากรอกชื่อหน่วยงาน")
                    elif len(clean_pass) < 6:
                        st.error("⚠️ รหัสผ่านต้องมีความยาวอย่างน้อย 6 ตัวอักษร")
                    else:
                        try:
                            supabase.table("agencies").insert({
                                "agency_code": clean_code,
                                "agency_name": clean_name,
                                "admin_email": new_email.strip() if new_email.strip() else "-",
                                "password": hash_password(clean_pass),
                            }).execute()
                            st.success("🎉 ลงทะเบียนสำเร็จ! นำรหัสและรหัสผ่านไปเข้าสู่ระบบได้ทันที")
                        except Exception as e:
                            st.error(f"⚠️ รหัสหน่วยงานซ้ำ หรือเกิดข้อผิดพลาด: {e}")
    st.stop()

# =========================================================
# --- 🖥️ 7. หน้าจอส่วนหลัก (Main UI) ---
# =========================================================
active_agency = st.session_state.current_agency
active_agency_name = st.session_state.current_agency_name

with st.sidebar:
    st.markdown("### 👤 ข้อมูลผู้ใช้งาน")
    st.info(f"**หน่วยงาน:** {active_agency_name}\n\n**รหัส:** `{active_agency}`")

    with st.expander("🔑 เปลี่ยนรหัสผ่าน"):
        with st.form("change_password_form", clear_on_submit=True):
            old_pwd = st.text_input("รหัสผ่านเดิม", type="password")
            new_pwd = st.text_input("รหัสผ่านใหม่ (อย่างน้อย 6 ตัวอักษร)", type="password")
            confirm_new_pwd = st.text_input("ยืนยันรหัสผ่านใหม่", type="password")
            btn_chg_pwd = st.form_submit_button("💾 บันทึกรหัสผ่านใหม่", type="primary", use_container_width=True)

            if btn_chg_pwd:
                if new_pwd != confirm_new_pwd:
                    st.error("❌ รหัสผ่านใหม่และการยืนยันรหัสผ่านไม่ตรงกัน")
                else:
                    ok_chg, msg_chg = change_agency_password(active_agency, old_pwd, new_pwd)
                    if ok_chg:
                        st.success(msg_chg)
                    else:
                        st.error(msg_chg)

    if st.button("🔄 รีเฟรชข้อมูลล่าสุดจาก Cloud", use_container_width=True):
        get_agency_years.clear()
        get_shared_data.clear()
        df_to_excel_bytes.clear()
        st.rerun()

    if st.button("🚪 ออกจากระบบ (Logout)", type="secondary", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# หัวข้อและแบนเนอร์หน่วยงาน
st.markdown("<div class='app-header'>🏛️ ระบบตรวจครุภัณฑ์ (Cloud)</div>", unsafe_allow_html=True)
st.markdown(
    f"""
    <div class='agency-banner'>
        <span>📌 <b>{html.escape(active_agency_name)}</b> ({html.escape(active_agency)})</span>
        <span class='agency-pill'>🔒 Secure Multi-Tenant</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# จัดการ URL Query Params (?scan=...) หลังล็อกอินแล้ว
scanned_param = st.query_params.get("scan", "")
if scanned_param:
    clean_scan = extract_scan_code(scanned_param)
    st.session_state.pending_scan_value = clean_scan
    st.session_state.active_search_query = clean_scan
    st.session_state.open_scanner = False
    st.session_state.trigger_popup_check = True
    st.session_state.nav_menu_radio = M_AUDIT
    st.query_params.clear()

# แถวเลือกปีงบประมาณ + จัดการไฟล์ Excel
available_years = get_agency_years(active_agency)
col_year_top, col_upload_top = st.columns([2, 3])

with col_year_top:
    selected_fiscal_year = st.selectbox(
        "📅 ปีงบประมาณ",
        options=available_years,
        key="global_fiscal_year_select",
    )
    year_key = selected_fiscal_year

with col_upload_top:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    with st.popover("📤 นำเข้า / ล้างข้อมูลบัญชีครุภัณฑ์ (Excel)", use_container_width=True):
        st.markdown(f"##### 📤 นำเข้าข้อมูล: **{active_agency_name}**")
        st.caption("รองรับไฟล์ .xlsx และ .xls (อัปโหลดทับข้อมูลตั้งต้นได้โดยไม่ลบผลการตรวจเดิม)")

        top_excel_upload = st.file_uploader("เลือกไฟล์ Excel", type=["xlsx", "xls"], key="top_uploader_key")

        if top_excel_upload:
            try:
                year_match = re.search(r"(25\d{2})", top_excel_upload.name)
                default_year = (
                    year_match.group(1)
                    if year_match
                    else (year_key if year_key != "รอการอัปโหลดไฟล์" else str(now_thai().year + 543))
                )
                upload_year = st.text_input("📌 ปีงบประมาณสำหรับไฟล์นี้ (เช่น 2570)", value=default_year)

                raw_excel = read_excel_source(top_excel_upload)
                p_df, m_code_col = parse_excel_dataframe(raw_excel)

                valid_upload_count = int(p_df[m_code_col].apply(is_valid_asset_code).sum()) if not p_df.empty else 0
                st.success(f"🎯 คอลัมน์รหัส: **'{m_code_col}'** | พบข้อมูลถูกต้อง **{valid_upload_count:,}** รายการ")

                if st.button("🚀 ยืนยันบันทึกขึ้น Cloud ทันที", type="primary", use_container_width=True, key="btn_confirm_upload_top"):
                    upload_dict = {}
                    clean_upload_year = str(upload_year).strip()
                    for _, r in p_df.iterrows():
                        c_val = str(r[m_code_col]).strip()
                        if not is_valid_asset_code(c_val):
                            continue
                        r_data = {str(k): ("" if pd.isna(v) else str(v).strip()) for k, v in r.items()}
                        upload_dict[c_val] = {
                            "agency_id": active_agency,
                            "fiscal_year": clean_upload_year,
                            "asset_code": c_val,
                            "row_data": r_data,
                        }

                    upload_rows = list(upload_dict.values())
                    if upload_rows and supabase:
                        progress_bar = st.progress(0, text="กำลังอัปโหลดข้อมูลขึ้น Cloud...")
                        batch_size = 200
                        total_batches = (len(upload_rows) + batch_size - 1) // batch_size
                        for b_idx, i in enumerate(range(0, len(upload_rows), batch_size), start=1):
                            supabase.table("agency_assets").upsert(
                                upload_rows[i : i + batch_size],
                                on_conflict="agency_id,fiscal_year,asset_code",
                            ).execute()
                            progress_bar.progress(
                                b_idx / total_batches,
                                text=f"อัปโหลดแล้ว {min(i + batch_size, len(upload_rows)):,}/{len(upload_rows):,} รายการ",
                            )

                        get_agency_years.clear()
                        get_shared_data.clear()
                        df_to_excel_bytes.clear()
                        st.session_state.cloud_save_success_toast = True
                        st.rerun()
                    else:
                        st.error("⚠️ ไม่พบข้อมูลรหัสครุภัณฑ์ที่ถูกต้องในไฟล์")
            except Exception as ex:
                st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {ex}")

        st.markdown("<hr style='margin: 14px 0px;'>", unsafe_allow_html=True)
        st.markdown("🧨 **ล้างข้อมูลทั้งปีงบประมาณ**")
        confirm_pass = st.text_input(
            f"กรอกรหัสผ่านเพื่อยืนยันการลบข้อมูลปี {year_key}",
            type="password",
            key="confirm_delete_pass",
        )
        if st.button(f"🗑️ ลบข้อมูลครุภัณฑ์ปี {year_key} ทั้งหมด", type="secondary", use_container_width=True):
            if not confirm_pass:
                st.warning("⚠️ กรุณากรอกรหัสผ่านก่อนกดยืนยัน")
            elif year_key == "รอการอัปโหลดไฟล์":
                st.warning("⚠️ ไม่มีข้อมูลปีงบประมาณให้ลบ")
            else:
                ok_pwd, _, err_pwd = authenticate_agency(active_agency, confirm_pass)
                if ok_pwd:
                    supabase.table("agency_assets").delete().eq("agency_id", active_agency).eq("fiscal_year", year_key).execute()
                    supabase.table("core_assetauditrecord").delete().eq("agency_id", active_agency).eq("fiscal_year", year_key).execute()
                    get_agency_years.clear()
                    get_shared_data.clear()
                    df_to_excel_bytes.clear()
                    st.session_state.cloud_delete_success_toast = True
                    st.rerun()
                else:
                    st.error(err_pwd or "❌ รหัสผ่านไม่ถูกต้อง")

# แสดงแจ้งเตือน Popup / Toast
if st.session_state.pop("cloud_save_success_toast", False):
    show_1sec_popup("✅ บันทึกข้อมูลขึ้น Cloud แล้ว", is_success=True)
if st.session_state.pop("cloud_delete_success_toast", False):
    show_1sec_popup("🗑️ ลบข้อมูลออกจาก Cloud แล้ว", is_success=True)
if "flash_success_msg" in st.session_state:
    st.toast(st.session_state.flash_success_msg, icon="✅")
    del st.session_state.flash_success_msg

# โหลดข้อมูลหลัก
df, target_column, current_year_key = get_shared_data(selected_fiscal_year, active_agency)
valid_mask = df[target_column].apply(is_valid_asset_code) if not df.empty else pd.Series(dtype=bool)
valid_df = df[valid_mask] if not df.empty else df

total_items = len(valid_df)
if total_items > 0:
    checked_mask = valid_df["สถานะการตรวจ"] == "ตรวจแล้ว"
    checked_items = int(checked_mask.sum())
    unchecked_items = int((valid_df["สถานะการตรวจ"] == "ยังไม่ตรวจ").sum())
    cond_counts = valid_df.loc[checked_mask, "สภาพครุภัณฑ์"].value_counts().to_dict()
    normal_count = int(cond_counts.get("ปกติ", 0))
    damaged_count = int(cond_counts.get("ชำรุด/เสียหาย", 0))
    obsolete_count = int(cond_counts.get("หมดความจำเป็น", 0))
else:
    checked_items = unchecked_items = normal_count = damaged_count = obsolete_count = 0
    cond_counts = {}

progress_pct = (checked_items / total_items * 100) if total_items > 0 else 0.0
bar_width = max(progress_pct, 1.5) if checked_items > 0 else 0.0

st.markdown(
    f"**ความคืบหน้า ({html.escape(selected_fiscal_year)}): {progress_pct:.2f}%** "
    f"(ตรวจแล้ว {checked_items:,} / {total_items:,} รายการ)"
)
st.markdown(
    f"<div class='progress-wrapper'><div class='progress-fill' style='width: {bar_width}%;'></div></div>",
    unsafe_allow_html=True,
)

# แถบ KPI 6 กล่อง + ช่อง "📋 สภาพอื่นๆ" (แสดงยอดสรุปอย่างเดียว ไม่ผูกกรองกับตารางด้านล่าง)
other_conditions = CONDITION_OPTIONS[3:]
col_kpis, col_other_cond = st.columns([6, 1.6])

with col_kpis:
    st.markdown(
        f"""
        <div class="kpi-grid">
            <div class="kpi-card kpi-blue"><div class="kpi-label">📦 ทั้งหมด</div><div class="kpi-val">{total_items:,}</div></div>
            <div class="kpi-card kpi-green"><div class="kpi-label">✔️ ตรวจแล้ว</div><div class="kpi-val">{checked_items:,}</div></div>
            <div class="kpi-card kpi-amber"><div class="kpi-label">⏳ ยังไม่ตรวจ</div><div class="kpi-val">{unchecked_items:,}</div></div>
            <div class="kpi-card kpi-green"><div class="kpi-label">✅ สภาพปกติ</div><div class="kpi-val">{normal_count:,}</div></div>
            <div class="kpi-card kpi-red"><div class="kpi-label">⚠️ ชำรุด/เสียหาย</div><div class="kpi-val">{damaged_count:,}</div></div>
            <div class="kpi-card"><div class="kpi-label">📦 หมดความจำเป็น</div><div class="kpi-val">{obsolete_count:,}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_other_cond:
    selected_top_other = st.selectbox(
        "📋 สภาพอื่นๆ",
        ["เลือกดูสภาพ..."] + other_conditions,
        key="top_other_metric_dropdown",
        label_visibility="visible",
    )
    if selected_top_other != "เลือกดูสภาพ...":
        other_count = int(cond_counts.get(selected_top_other, 0))
        st.markdown(
            f"<div style='font-size: 14px; font-weight: 700; color: #1d4ed8; text-align: center; margin-top: -10px;'>"
            f"จำนวน: {other_count:,} รายการ</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='font-size: 12px; color: #64748b; text-align: center; margin-top: -10px;'>เลือกดูจำนวน</div>",
            unsafe_allow_html=True,
        )

other_summary = [f"{c}: **{cond_counts.get(c, 0):,}**" for c in other_conditions if cond_counts.get(c, 0) > 0]
if other_summary:
    st.caption("📋 สภาพอื่นๆ ที่มีผลการตรวจแล้ว: " + " | ".join(other_summary))

if total_items == 0:
    st.info("ℹ️ ยังไม่มีข้อมูลครุภัณฑ์ในระบบ กรุณากดปุ่ม **'📤 นำเข้า / ล้างข้อมูลบัญชีครุภัณฑ์ (Excel)'** ด้านบนครับ")

# เมนูนำทางเรียงตามลำดับเดิม
selected_menu = st.radio(
    "เลือกเมนู:",
    options=[M_SEARCH, M_AUDIT, M_QR, M_EXPORT],
    horizontal=True,
    label_visibility="collapsed",
    key="nav_menu_radio",
)
st.markdown("<hr style='margin: 8px 0px 14px 0px;'>", unsafe_allow_html=True)

# =========================================================
# ================= MENU 1: ค้นหา / แก้ไข =================
# =========================================================
if selected_menu == M_SEARCH:
    st.subheader(f"🔍 ค้นหาและจัดการข้อมูลครุภัณฑ์ ({selected_fiscal_year})")

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        search_query = st.text_input("พิมพ์ค้นหา:", placeholder="ชื่อ, รหัส, สถานที่, สภาพ...", key="search_main_1")
    with col_s2:
        condition_filter = st.selectbox("กรองสภาพครุภัณฑ์", ["ทั้งหมด"] + CONDITION_OPTIONS, key="filter_cond_main_1")
    with col_s3:
        status_filter = st.selectbox("กรองสถานะการตรวจ", ["ทั้งหมด"] + STATUS_OPTIONS, key="filter_main_1")
    with col_s4:
        inspector_filter = st.text_input("กรองผู้ตรวจ:", placeholder="ชื่อผู้ตรวจสอบ...", key="filter_inspector_main")

    display_df = valid_df.copy()

    if status_filter != "ทั้งหมด":
        display_df = display_df[display_df["สถานะการตรวจ"] == status_filter]
    if condition_filter != "ทั้งหมด":
        display_df = display_df[display_df["สภาพครุภัณฑ์"] == condition_filter]
    if inspector_filter:
        display_df = display_df[
            display_df["ผู้ตรวจ"].astype(str).str.contains(inspector_filter, case=False, na=False, regex=False)
        ]
    if search_query:
        display_df = display_df[
            display_df.astype(str)
            .apply(lambda col: col.str.contains(search_query, case=False, na=False, regex=False))
            .any(axis=1)
        ]

    st.caption(f"แสดงผล **{len(display_df):,}** จากทั้งหมด **{total_items:,}** รายการ")
    st.dataframe(display_df, use_container_width=True, height=420)

    if not display_df.empty:
        col_dl, _ = st.columns([1.6, 3.4])
        with col_dl:
            st.download_button(
                label="📥 ดาวน์โหลดรายการที่กรองนี้ (Excel)",
                data=df_to_excel_bytes(display_df),
                file_name=f"รายงานครุภัณฑ์_{active_agency}_{selected_fiscal_year}_{now_thai().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    st.markdown("<hr style='margin: 16px 0px;'>", unsafe_allow_html=True)
    enable_admin_tools = st.checkbox("⚙️ เปิดโหมดผู้ดูแลระบบ: แก้ไขรายละเอียด / เพิ่มครุภัณฑ์ใหม่", value=False)

    if enable_admin_tools:
        with st.container(border=True):
            mode_select = st.radio(
                "เลือกโหมด:",
                ["✏️ แก้ไขข้อมูลครุภัณฑ์เดิม", "➕ เพิ่มรายการครุภัณฑ์ใหม่ขึ้น Cloud"],
                horizontal=True,
            )
            non_editable = {"สภาพครุภัณฑ์", "สถานะการตรวจ", "ผู้ตรวจ", "วันเดือนปี เวลา ที่ทำการตรวจสอบ"}
            editable_cols = [c for c in df.columns if c not in non_editable and c != target_column]
            if "หมายเหตุ" not in editable_cols and "หมายเหตุ" in df.columns:
                editable_cols.append("หมายเหตุ")

            if mode_select == "✏️ แก้ไขข้อมูลครุภัณฑ์เดิม":
                asset_list = valid_df[target_column].tolist() if not valid_df.empty else []
                if not asset_list:
                    st.warning("⚠️ ยังไม่มีรายการครุภัณฑ์ให้แก้ไข")
                else:
                    edit_target = st.selectbox(
                        f"เลือกหมายเลขครุภัณฑ์ ({target_column})",
                        options=asset_list,
                        key="cloud_edit_item_select",
                    )
                    target_row = df[df[target_column].astype(str).str.strip() == str(edit_target).strip()].iloc[0]

                    with st.form("cloud_edit_asset_form"):
                        updated_values = {}
                        cols_ui = st.columns(3)
                        for idx, col_name in enumerate(editable_cols):
                            with cols_ui[idx % 3]:
                                cur_val = str(target_row.get(col_name, "-"))
                                if cur_val in {"nan", "None"}:
                                    cur_val = "-"
                                updated_values[col_name] = st.text_input(
                                    col_name,
                                    value=cur_val,
                                    key=f"edit_field_{col_name}_{edit_target}",
                                )

                        b1, b2 = st.columns(2)
                        with b1:
                            save_edit = st.form_submit_button("☁️ บันทึกการแก้ไข", type="primary", use_container_width=True)
                        with b2:
                            delete_item = st.form_submit_button("🗑️ ลบรายการนี้", type="secondary", use_container_width=True)

                        if save_edit:
                            note_val = updated_values.get("หมายเหตุ", "-") or "-"
                            updated_values["หมายเหตุ_ข้อมูลหลัก"] = note_val
                            ok = save_progress_to_supabase(
                                asset_code=edit_target,
                                condition=target_row["สภาพครุภัณฑ์"],
                                status=target_row["สถานะการตรวจ"],
                                note=note_val,
                                inspector=target_row["ผู้ตรวจ"],
                                timestamp=target_row["วันเดือนปี เวลา ที่ทำการตรวจสอบ"],
                                fiscal_year=current_year_key,
                                agency_id=active_agency,
                                extra_dict=updated_values,
                            )
                            if ok:
                                get_shared_data.clear()
                                df_to_excel_bytes.clear()
                                st.session_state.cloud_save_success_toast = True
                                st.rerun()

                        if delete_item:
                            if delete_asset_from_supabase(edit_target, current_year_key, active_agency):
                                get_shared_data.clear()
                                df_to_excel_bytes.clear()
                                st.session_state.cloud_delete_success_toast = True
                                st.rerun()
            else:
                with st.form("cloud_add_asset_form"):
                    new_code = st.text_input(f"🌟 {target_column} (จำเป็นต้องกรอกและมีตัวเลข)")
                    new_values = {}
                    cols_ui = st.columns(3)
                    for idx, col_name in enumerate(editable_cols):
                        with cols_ui[idx % 3]:
                            new_values[col_name] = st.text_input(col_name, value="-", key=f"new_col_{idx}")

                    if st.form_submit_button("➕ เพิ่มรายการใหม่ขึ้น Cloud", type="primary", use_container_width=True):
                        clean_new = new_code.strip()
                        existing_codes = set(df[target_column].astype(str).str.strip().values) if not df.empty else set()
                        if not is_valid_asset_code(clean_new):
                            st.error(f"⚠️ กรุณากรอก '{target_column}' ให้ถูกต้อง")
                        elif clean_new in existing_codes:
                            st.warning("⚠️ หมายเลขครุภัณฑ์นี้มีอยู่ในระบบแล้ว")
                        else:
                            note_val = new_values.get("หมายเหตุ", "-") or "-"
                            new_values["หมายเหตุ_ข้อมูลหลัก"] = note_val
                            save_year = (
                                current_year_key
                                if current_year_key != "รอการอัปโหลดไฟล์"
                                else str(now_thai().year + 543)
                            )
                            ok = save_progress_to_supabase(
                                asset_code=clean_new,
                                condition="-",
                                status="ยังไม่ตรวจ",
                                note=note_val,
                                inspector="-",
                                timestamp="-",
                                fiscal_year=save_year,
                                agency_id=active_agency,
                                extra_dict=new_values,
                            )
                            if ok:
                                get_agency_years.clear()
                                get_shared_data.clear()
                                df_to_excel_bytes.clear()
                                st.session_state.cloud_save_success_toast = True
                                st.rerun()

# =========================================================
# ================= MENU 2: ตรวจนับ / บันทึก =================
# =========================================================
elif selected_menu == M_AUDIT:
    st.subheader(f"📝 ตรวจครุภัณฑ์ / บันทึกผลการตรวจ ({selected_fiscal_year})")

    if st.session_state.pop("pending_clear_scan", False):
        st.session_state.scanned_asset_box = ""
        st.session_state.active_search_query = ""
    if "pending_scan_value" in st.session_state:
        st.session_state.scanned_asset_box = st.session_state.pop("pending_scan_value")

    if "open_scanner" not in st.session_state:
        st.session_state.open_scanner = False
    if "continuous_scan" not in st.session_state:
        st.session_state.continuous_scan = False
    if "last_inspector" not in st.session_state:
        st.session_state.last_inspector = ""

    def on_asset_input_change():
        raw_val = st.session_state.get("scanned_asset_box", "").strip()
        if raw_val:
            clean_code = extract_scan_code(raw_val)
            st.session_state.scanned_asset_box = clean_code
            st.session_state.active_search_query = clean_code
            st.session_state.open_scanner = False
            st.session_state.trigger_popup_check = True

    with st.container(border=True):
        st.markdown("##### 🔎 สแกน QR Code หรือกรอกหมายเลขครุภัณฑ์")

        btn_label = "❌ ปิดกล้องสแกน QR Code" if st.session_state.open_scanner else "📷 เปิดกล้องสแกน QR Code หมายเลขพัสดุ"
        if st.button(
            btn_label,
            use_container_width=True,
            type="primary" if not st.session_state.open_scanner else "secondary",
        ):
            st.session_state.open_scanner = not st.session_state.open_scanner
            st.rerun()

        if st.session_state.open_scanner:
            render_auto_submit_qr_scanner()

        scanned_code_input = st.text_input(
            "กรอกหมายเลขครุภัณฑ์ เพื่อค้นหา",
            key="scanned_asset_box",
            placeholder="สแกน QR Code หรือพิมพ์เลขครุภัณฑ์ / ชื่อรายการ...",
            on_change=on_asset_input_change,
        )

        c_find, c_clear, c_cont = st.columns([1.4, 1, 2.6])
        with c_find:
            search_clicked = st.button("🔍 ค้นหา", key="btn_search_mid", type="primary", use_container_width=True)
        with c_clear:
            if st.button("🧹 ล้างคำค้นหา", key="btn_clear_mid", use_container_width=True):
                st.session_state.pending_clear_scan = True
                st.rerun()
        with c_cont:
            st.checkbox(
                "🔄 โหมดเดินตรวจต่อเนื่อง (บันทึกแล้วเปิดกล้องสแกนชิ้นถัดไปอัตโนมัติ)",
                key="continuous_scan",
            )

    if search_clicked and scanned_code_input.strip():
        clean_code = extract_scan_code(scanned_code_input)
        st.session_state.active_search_query = clean_code
        st.session_state.open_scanner = False
        st.session_state.trigger_popup_check = True

    current_query = st.session_state.get("active_search_query", "")

    if not current_query:
        st.info("👆 กด **เปิดกล้องสแกน QR Code** หรือพิมพ์หมายเลขครุภัณฑ์ด้านบนเพื่อค้นหาและบันทึกผลการตรวจ")
    else:
        search_term = extract_scan_code(current_query)
        exact_match = valid_df[valid_df[target_column].astype(str).str.strip().str.lower() == search_term.lower()]
        if not exact_match.empty:
            matched_mob = exact_match
        else:
            matched_mob = valid_df[
                valid_df[target_column].astype(str).str.contains(search_term, case=False, na=False, regex=False)
            ]
        if matched_mob.empty:
            matched_mob = valid_df[
                valid_df.astype(str)
                .apply(lambda col: col.str.contains(search_term, case=False, na=False, regex=False))
                .any(axis=1)
            ]

        if st.session_state.pop("trigger_popup_check", False):
            if not matched_mob.empty:
                show_1sec_popup("✅ ค้นพบข้อมูลครุภัณฑ์", is_success=True)
            else:
                show_1sec_popup("❌ ไม่พบข้อมูล / QR ไม่ถูกต้อง", is_success=False)

        if matched_mob.empty:
            st.warning(f"⚠️ ไม่พบครุภัณฑ์ที่ตรงกับคำค้นหา **'{search_term}'** ในปีงบประมาณ {selected_fiscal_year}")
        else:
            st.success(f"🎯 พบข้อมูลครุภัณฑ์ที่ตรงกับรหัส/คำค้นหา: **{len(matched_mob):,}** รายการ")

            if len(matched_mob) > 1:
                pick_code = st.selectbox(
                    "เลือกรายการครุภัณฑ์ที่ต้องการบันทึกผล:",
                    options=matched_mob[target_column].tolist(),
                    key="multi_match_picker",
                )
                target_row_data = matched_mob[matched_mob[target_column] == pick_code].iloc[0]
            else:
                target_row_data = matched_mob.iloc[0]

            mob_target = str(target_row_data[target_column]).strip()

            with st.expander("📋 ดูรายละเอียดคอลัมน์ทั้งหมดของรายการนี้", expanded=False):
                st.dataframe(matched_mob, use_container_width=True)

            st.markdown(
                f"### 📝 บันทึก / แก้ไขผลการตรวจสำหรับรหัส: <span style='color:#1d4ed8;'>{html.escape(mob_target)}</span>",
                unsafe_allow_html=True,
            )

            with st.container(border=True):
                col_info_badge, col_info_details = st.columns([1.5, 1.5])
                with col_info_badge:
                    st.markdown(
                        f"<div style='font-size: 14px; font-weight: 600; margin-bottom: 4px; color: #31333F;'>"
                        f"สถานะปัจจุบัน ({html.escape(selected_fiscal_year)})</div>",
                        unsafe_allow_html=True,
                    )
                    render_status_badge(
                        target_row_data["สถานะการตรวจ"],
                        target_row_data["สภาพครุภัณฑ์"],
                        target_row_data["ผู้ตรวจ"],
                    )
                with col_info_details:
                    st.markdown(f"**ชื่อรายการ:** {html.escape(str(target_row_data.get('รายการ', '-')))}")
                    st.markdown(f"**สถานที่/อยู่ที่:** {html.escape(str(target_row_data.get('อยู่ที่', '-')))}")

                cur_cond = str(target_row_data["สภาพครุภัณฑ์"]).strip()
                default_cond_idx = CONDITION_OPTIONS.index(cur_cond) if cur_cond in CONDITION_OPTIONS else 0
                default_status_idx = 0

                cur_note = str(target_row_data["หมายเหตุ"]).strip()
                if cur_note in {"-", "nan", "None"}:
                    cur_note = ""

                cur_insp = str(target_row_data["ผู้ตรวจ"]).strip()
                if cur_insp in {"-", "nan", "None", ""}:
                    cur_insp = st.session_state.get("last_inspector", "")

                with st.form(key=f"audit_form_{mob_target}", border=False):
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    with mc1:
                        mob_condition = st.selectbox("1. สภาพครุภัณฑ์", CONDITION_OPTIONS, index=default_cond_idx)
                    with mc2:
                        mob_status = st.selectbox("2. สถานะการตรวจ", STATUS_OPTIONS, index=default_status_idx)
                    with mc3:
                        mob_note = st.text_input("หมายเหตุ (รายละเอียดเพิ่มเติม)", value=cur_note)
                    with mc4:
                        mob_inspector = st.text_input("3. ผู้ตรวจ (ระบบจำชื่อให้ครั้งถัดไป)", value=cur_insp)

                    m_btn_col, m_save_status_col = st.columns([1.2, 1.8])
                    with m_btn_col:
                        mob_submit = st.form_submit_button(
                            "💾 บันทึกผลการตรวจทันที",
                            type="primary",
                            use_container_width=True,
                        )
                    with m_save_status_col:
                        render_save_status_badge(
                            target_row_data["สถานะการตรวจ"],
                            target_row_data["วันเดือนปี เวลา ที่ทำการตรวจสอบ"],
                        )

                    if mob_submit:
                        current_time = now_thai().strftime("%d/%m/%Y %H:%M:%S")
                        clean_insp = mob_inspector.strip()
                        if clean_insp:
                            st.session_state.last_inspector = clean_insp

                        if mob_status == "ยังไม่ตรวจ":
                            m_cond, m_stat, m_insp, m_time = "-", "ยังไม่ตรวจ", "-", "-"
                        else:
                            m_cond = mob_condition
                            m_stat = mob_status
                            m_insp = clean_insp if clean_insp else "-"
                            m_time = current_time

                        m_note = mob_note.strip() if mob_note.strip() else "-"

                        ok = save_progress_to_supabase(
                            asset_code=mob_target,
                            condition=m_cond,
                            status=m_stat,
                            note=m_note,
                            inspector=m_insp,
                            timestamp=m_time,
                            fiscal_year=current_year_key,
                            agency_id=active_agency,
                        )
                        if ok:
                            get_shared_data.clear()
                            df_to_excel_bytes.clear()
                            st.session_state.flash_success_msg = f"บันทึก {mob_target} ({m_cond}) เรียบร้อยแล้ว!"
                            if st.session_state.continuous_scan:
                                st.session_state.pending_clear_scan = True
                                st.session_state.open_scanner = True
                            else:
                                st.session_state.open_scanner = False
                            st.rerun()

# =========================================================
# ================= MENU 3: สร้าง QR Code =================
# =========================================================
elif selected_menu == M_QR:
    st.subheader(f"🏷️ สร้างป้าย QR Code ({selected_fiscal_year})")
    qr_options_list = valid_df[target_column].tolist() if not valid_df.empty else []

    if not qr_options_list:
        st.info("ℹ️ ยังไม่มีรายการครุภัณฑ์สำหรับสร้าง QR Code")
    else:
        selected_qr_item = st.selectbox(
            "เลือกหมายเลขครุภัณฑ์ที่ต้องการสร้างป้าย QR:",
            options=qr_options_list,
            key="gen_qr_tab",
        )
        if selected_qr_item:
            byte_im = generate_qr_label_png(str(selected_qr_item), APP_BASE_URL)
            st.image(byte_im, caption=f"ป้าย QR Code: {selected_qr_item}", width=280)
            st.download_button(
                label=f"📥 ดาวน์โหลดรูปป้าย QR ({selected_qr_item})",
                data=byte_im,
                file_name=f"QRCode_Label_{selected_qr_item}.png",
                mime="image/png",
                type="primary",
            )

# =========================================================
# ================= MENU 4: ส่งออก Excel =================
# =========================================================
elif selected_menu == M_EXPORT:
    st.subheader(f"📥 ส่งออกรายงานสรุปผลการตรวจสอบ ({selected_fiscal_year})")
    if valid_df.empty:
        st.info("ℹ️ ยังไม่มีข้อมูลสำหรับส่งออกรายงาน")
    else:
        st.write(f"พร้อมส่งออกข้อมูลครุภัณฑ์ทั้งหมด **{total_items:,}** รายการ (ตรวจแล้ว **{checked_items:,}** รายการ)")
        st.download_button(
            label=f"📊 ดาวน์โหลดรายงาน Excel ({selected_fiscal_year})",
            data=df_to_excel_bytes(valid_df),
            file_name=f"รายงานผลการตรวจครุภัณฑ์_{active_agency}_{selected_fiscal_year}_{now_thai().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
