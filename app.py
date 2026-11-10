import sys
import os
import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, timedelta
import re
import qrcode
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import numpy as np
from supabase import create_client, Client

# --- 🔌 ตั้งค่าการเชื่อมต่อ Supabase Cloud ผ่าน st.secrets ---
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://vcznzjgcfixautswrurp.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "sb_publishable_KooBDzoTj9aO1NVSEyYfjw_R1v__BpY")

@st.cache_resource
def init_supabase():
    try:
        if SUPABASE_URL and SUPABASE_KEY:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception:
        return None
    return None

supabase: Client = init_supabase()

# ตั้งค่าหน้าเว็บให้เป็นแบบ Wide
st.set_page_config(
    page_title="ระบบตรวจครุภัณฑ์ (Secure Cloud)",
    page_icon="🏛️",
    layout="wide"
)

st.markdown("""
    <style>
    .block-container {
        padding-top: 4.5rem !important;
        padding-bottom: 2rem !important;
    }
    .app-header {
        font-size: 28px;
        font-weight: 700;
        color: #1f2937;
        margin-top: 5px;
        margin-bottom: 12px;
        line-height: 1.5 !important;
    }
    .agency-banner {
        background: linear-gradient(135deg, #1e3a8a, #3b82f6);
        color: white;
        padding: 10px 18px;
        border-radius: 8px;
        font-weight: 600;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .stAlert {
        padding: 8px 14px !important;
        margin-bottom: 8px !important;
    }
    .status-box-green {
        background-color: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
        padding: 8px 14px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 15px;
        display: flex;
        align-items: center;
        min-height: 40px;
    }
    .status-box-red {
        background-color: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
        padding: 8px 14px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 15px;
        display: flex;
        align-items: center;
        min-height: 40px;
    }
    .progress-wrapper {
        background-color: #e5e7eb;
        border-radius: 10px;
        width: 100%;
        height: 22px;
        overflow: hidden;
        margin-top: 6px;
        margin-bottom: 14px;
        box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
    }
    .progress-fill {
        background: linear-gradient(90deg, #22c55e, #16a34a);
        height: 100%;
        border-radius: 10px;
        transition: width 0.4s ease;
    }
    [data-testid="stMetricValue"] {
        font-size: 20px !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 11px !important;
    }
    [data-testid="stMetric"] {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 8px 8px;
        border-radius: 8px;
    }

    /* 🟢 ตกแต่ง st.radio ให้วงกลมและตัวหนังสือเมื่อเลือกเป็น "สีเขียว" */
    div.row-widget.stRadio > div[role="radiogroup"] {
        background-color: #f8fafc;
        padding: 10px 15px;
        border-radius: 12px;
        border: 1px solid #cbd5e1;
        display: flex;
        justify-content: space-around;
    }
    div.row-widget.stRadio div[role="radiogroup"] label input:checked + div {
        background-color: #22c55e !important;
        border-color: #22c55e !important;
    }
    div.row-widget.stRadio div[role="radiogroup"] label input:checked + div::after {
        background-color: #ffffff !important;
    }
    div.row-widget.stRadio div[role="radiogroup"] label:has(input:checked) p {
        color: #15803d !important;
        font-weight: 800 !important;
    }

    /* 💬 สไตล์สำหรับป๊อบอัพแจ้งเตือน 1 วินาที แล้วหายไปเองอัตโนมัติ */
    @keyframes popupFadeOut {
        0% { opacity: 1; transform: translate(-50%, -50%) scale(0.95); }
        15% { opacity: 1; transform: translate(-50%, -50%) scale(1.02); }
        75% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
        100% { opacity: 0; transform: translate(-50%, -50%) scale(0.95); visibility: hidden; }
    }
    .auto-popup-badge {
        position: fixed;
        top: 35%;
        left: 50%;
        transform: translate(-50%, -50%);
        z-index: 999999;
        padding: 18px 32px;
        border-radius: 12px;
        font-size: 20px;
        font-weight: 700;
        color: #ffffff;
        box-shadow: 0 10px 25px rgba(0,0,0,0.25);
        pointer-events: none;
        animation: popupFadeOut 1.2s ease-in-out forwards;
        text-align: center;
    }
    .popup-success {
        background-color: rgba(22, 163, 74, 0.95);
        border: 2px solid #bbf7d0;
    }
    .popup-error {
        background-color: rgba(220, 38, 38, 0.95);
        border: 2px solid #fecaca;
    }
    </style>
""", unsafe_allow_html=True)

# =========================================================
# --- 🛠️ ฟังก์ชันหลักทั้งหมดของระบบ ---
# =========================================================
header_row = 4

def show_1sec_popup(message, is_success=True):
    cls = "popup-success" if is_success else "popup-error"
    st.markdown(f"<div class='auto-popup-badge {cls}'>{message}</div>", unsafe_allow_html=True)

def is_valid_asset_code(val):
    if pd.isna(val):
        return False
    val_str = str(val).strip()
    if val_str == '' or val_str.lower() == 'nan' or val_str == '-':
        return False
    return bool(re.search(r'\d', val_str))

def parse_local_excel_file(filepath):
    if filepath.endswith('.csv'):
        raw_df = pd.read_csv(filepath, header=None)
    else:
        try:
            raw_df = pd.read_excel(filepath, header=None, engine='openpyxl')
        except Exception:
            raw_df = pd.read_excel(filepath, header=None, engine='xlrd')

    top_cols = raw_df.iloc[header_row].fillna('').astype(str).str.strip()
    sub_cols = raw_df.iloc[header_row + 1].fillna('').astype(str).str.strip()

    combined_columns = []
    for t, s in zip(top_cols, sub_cols):
        if s and s != 'None' and s != t:
            combined_columns.append(f"{t} ({s})" if t and t != 'None' else s)
        else:
            combined_columns.append(t if t and t != 'None' else 'Unnamed')

    df = raw_df.iloc[header_row + 2:].copy()
    df.columns = [str(c).strip() for c in combined_columns]
    df = df.dropna(how='all').reset_index(drop=True)

    potential_cols = [c for c in df.columns if any(k in str(c) for k in ['หมายเลขครุภัณฑ์', 'รหัส', 'เลข'])]
    target_col = potential_cols[0] if potential_cols else df.columns[0]
    return df, target_col

@st.cache_data(ttl=10)
def get_agency_years(agency_id):
    years_set = set()
    # หากเป็นหน่วยงานหลัก cgduthai ให้มีปีงบประมาณตั้งต้น 2570, 2569, 2568 เสมอ
    if agency_id in ["cgduthai", "default_agency"]:
        years_set.update(["2570", "2569", "2568"])

    if supabase:
        try:
            res = supabase.table("agency_assets").select("fiscal_year").eq("agency_id", agency_id).execute()
            if res.data:
                for r in res.data:
                    if r.get("fiscal_year"):
                        years_set.add(str(r["fiscal_year"]).strip())
        except Exception:
            pass

    if years_set:
        return sorted(list(years_set), reverse=True)
    return ["รอการอัปโหลดไฟล์"]

@st.cache_data(ttl=60)
def get_shared_data(fiscal_year_str, agency_id):
    target_col = "หมายเลขครุภัณฑ์"
    default_columns = [
        target_col, "รายการ", "อยู่ที่",
        "สภาพครุภัณฑ์", "สถานะการตรวจ", "หมายเหตุ", "ผู้ตรวจ", "วันเดือนปี เวลา ที่ทำการตรวจสอบ"
    ]

    if fiscal_year_str == "รอการอัปโหลดไฟล์":
        return pd.DataFrame(columns=default_columns), target_col, "รอการอัปโหลดไฟล์"

    if "2568" in str(fiscal_year_str):
        year_key = "2568"
    elif "2569" in str(fiscal_year_str):
        year_key = "2569"
    elif "2570" in str(fiscal_year_str):
        year_key = "2570"
    else:
        year_key = str(fiscal_year_str).strip()

    df = None

    # 1. ดึงจากตาราง agency_assets ของหน่วยงานนั้นก่อน
    if supabase:
        try:
            asset_res = supabase.table("agency_assets").select("asset_code, row_data").eq("agency_id", agency_id).eq("fiscal_year", year_key).execute()
            if asset_res.data and len(asset_res.data) > 0:
                rows = [item["row_data"] for item in asset_res.data if isinstance(item.get("row_data"), dict)]
                if rows:
                    df = pd.DataFrame(rows)
                    potential_cols = [c for c in df.columns if any(k in str(c) for k in ['หมายเลขครุภัณฑ์', 'รหัส', 'เลข'])]
                    target_col = potential_cols[0] if potential_cols else df.columns[0]
        except Exception:
            df = None

    # 2. หากไม่มีใน agency_assets และเป็น cgduthai ให้ดึงจากไฟล์ Excel ใน GitHub
    if df is None:
        if agency_id in ["cgduthai", "default_agency"]:
            if year_key == "2568":
                file_candidates = ["default_asset_2568.xlsx", "default_asset_2568.xls"]
            elif year_key == "2569":
                file_candidates = ["default_asset_2569.xlsx", "default_asset_2569.xls"]
            else:
                file_candidates = [f"default_asset_{year_key}.xlsx", "default_asset.xlsx", "default_asset.xls", "default_asset_2570.xlsx"]

            default_file = None
            for f in file_candidates:
                if os.path.exists(f):
                    default_file = f
                    break

            if default_file:
                df, target_col = parse_local_excel_file(default_file)
            else:
                df = pd.DataFrame(columns=default_columns)
        else:
            df = pd.DataFrame(columns=default_columns)

    audit_cols = ['สภาพครุภัณฑ์', 'สถานะการตรวจ', 'หมายเหตุ', 'ผู้ตรวจ', 'วันเดือนปี เวลา ที่ทำการตรวจสอบ']
    for col in audit_cols:
        if col not in df.columns:
            if col == 'สถานะการตรวจ':
                df[col] = 'ยังไม่ตรวจ'
            else:
                df[col] = '-'

    for col in df.columns:
        df[col] = df[col].astype(str).replace('nan', '-').replace('None', '-')

    # 3. ดึงผลการตรวจและข้อมูลที่แก้ไข/เพิ่มใหม่ (||ASSET_DATA||) จาก core_assetauditrecord
    if supabase:
        try:
            response = supabase.table("core_assetauditrecord").select("*").eq("fiscal_year", year_key).eq("agency_id", agency_id).execute()
            saved_data = response.data

            if saved_data:
                new_cloud_rows = []
                for row in saved_data:
                    code = str(row['asset_code']).strip()
                    raw_note = str(row['note']) if pd.notna(row['note']) else '-'

                    actual_note = raw_note
                    extra_info = {}
                    if "||ASSET_DATA||" in raw_note:
                        parts = raw_note.split("||ASSET_DATA||", 1)
                        actual_note = parts[0] if parts[0] else '-'
                        try:
                            extra_info = json.loads(parts[1])
                        except Exception:
                            extra_info = {}

                    mask = df[target_col].astype(str).str.strip() == code
                    if mask.any():
                        df.loc[mask, 'สภาพครุภัณฑ์'] = str(row['condition']) if pd.notna(row['condition']) else '-'
                        df.loc[mask, 'สถานะการตรวจ'] = str(row['status']) if pd.notna(row['status']) else 'ยังไม่ตรวจ'
                        df.loc[mask, 'ผู้ตรวจ'] = str(row['inspector']) if pd.notna(row['inspector']) else '-'
                        df.loc[mask, 'วันเดือนปี เวลา ที่ทำการตรวจสอบ'] = str(row['updated_at']) if pd.notna(row['updated_at']) else '-'

                        if actual_note != '-' and actual_note != '':
                            df.loc[mask, 'หมายเหตุ'] = actual_note
                        elif extra_info and 'หมายเหตุ_ข้อมูลหลัก' in extra_info:
                            df.loc[mask, 'หมายเหตุ'] = extra_info['หมายเหตุ_ข้อมูลหลัก']

                        for col_k, val_v in extra_info.items():
                            if col_k in df.columns and col_k != 'หมายเหตุ_ข้อมูลหลัก':
                                df.loc[mask, col_k] = str(val_v)
                    else:
                        new_r = {c: '-' for c in df.columns}
                        new_r[target_col] = code
                        new_r['สภาพครุภัณฑ์'] = str(row['condition']) if pd.notna(row['condition']) else '-'
                        new_r['สถานะการตรวจ'] = str(row['status']) if pd.notna(row['status']) else 'ยังไม่ตรวจ'
                        new_r['หมายเหตุ'] = actual_note if actual_note != '-' else extra_info.get('หมายเหตุ_ข้อมูลหลัก', '-')
                        new_r['ผู้ตรวจ'] = str(row['inspector']) if pd.notna(row['inspector']) else '-'
                        new_r['วันเดือนปี เวลา ที่ทำการตรวจสอบ'] = str(row['updated_at']) if pd.notna(row['updated_at']) else '-'

                        for col_k, val_v in extra_info.items():
                            if col_k in df.columns and col_k != 'หมายเหตุ_ข้อมูลหลัก':
                                new_r[col_k] = str(val_v)
                        new_cloud_rows.append(new_r)

                if new_cloud_rows:
                    df = pd.concat([df, pd.DataFrame(new_cloud_rows)], ignore_index=True)

        except Exception as e:
            st.error(f"⚠️ เกิดข้อผิดพลาดในการโหลดข้อมูลจาก Supabase: {e}")

    return df, target_col, year_key

def save_progress_to_supabase(asset_code, condition, status, note, inspector, timestamp, fiscal_year, agency_id, extra_dict=None):
    if not supabase:
        st.error("⚠️ ไม่ได้เชื่อมต่อกับ Supabase Cloud")
        return False
    try:
        clean_code = str(asset_code).strip()
        existing = supabase.table("core_assetauditrecord").select("id, note").eq("asset_code", clean_code).eq("fiscal_year", fiscal_year).eq("agency_id", agency_id).execute()

        saved_extra = {}
        record_id = None
        if existing.data:
            record_id = existing.data[0].get("id")
            old_note = str(existing.data[0].get("note", ""))
            if "||ASSET_DATA||" in old_note:
                try:
                    saved_extra = json.loads(old_note.split("||ASSET_DATA||", 1)[1])
                except Exception:
                    saved_extra = {}

        clean_note = str(note).split("||ASSET_DATA||")[0].strip()
        if not clean_note:
            clean_note = "-"

        if extra_dict is not None:
            saved_extra.update(extra_dict)
        saved_extra['หมายเหตุ_ข้อมูลหลัก'] = clean_note

        final_note = f"{clean_note}||ASSET_DATA||{json.dumps(saved_extra, ensure_ascii=False)}" if saved_extra else clean_note

        data_payload = {
            "asset_code": clean_code,
            "condition": condition,
            "status": status,
            "note": final_note,
            "inspector": inspector,
            "updated_at": timestamp,
            "fiscal_year": fiscal_year,
            "agency_id": agency_id
        }

        if record_id:
            supabase.table("core_assetauditrecord").update(data_payload).eq("id", record_id).execute()
        else:
            supabase.table("core_assetauditrecord").insert(data_payload).execute()

        return True
    except Exception as e:
        st.error(f"⚠️ ไม่สามารถบันทึกลง Supabase ได้: {e}")
        return False

def delete_asset_from_supabase(asset_code, fiscal_year, agency_id):
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

def render_status_badge(status_val, cond_val, inspector_val):
    if status_val == 'ตรวจแล้ว':
        detail = f" (สภาพ: {cond_val} | ผู้ตรวจ: {inspector_val})" if cond_val != '-' else ""
        st.markdown(f"<div class='status-box-green'>✅ ผ่านการตรวจแล้ว{detail}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='status-box-red'>❌ ยังไม่ได้ตรวจ</div>", unsafe_allow_html=True)

def render_save_status_badge(status_val, timestamp_val):
    if status_val == 'ตรวจแล้ว':
        time_info = f" (เมื่อ: {timestamp_val})" if timestamp_val and timestamp_val != '-' else ""
        st.markdown(f"<div class='status-box-green'>✅ รายการนี้ได้บันทึกแล้ว{time_info}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='status-box-red'>❌ รายการนี้ยังไม่ได้บันทึก</div>", unsafe_allow_html=True)

def render_auto_submit_qr_scanner():
    scanner_html = """
    <div style="background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
        <div id="qr-reader" style="width: 100%; max-width: 380px; margin: 0 auto;"></div>
        <div id="qr-result" style="margin-top: 8px; font-family: sans-serif; font-size: 14px; color: #16a34a; font-weight: bold;">
            📷 กำลังเปิดกล้อง... ส่องไปที่ป้าย QR Code
        </div>
    </div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        const html5QrCode = new Html5Qrcode("qr-reader");
        const qrConfig = { fps: 15, qrbox: { width: 220, height: 220 } };
        let isSubmitted = false;
        
        html5QrCode.start(
            { facingMode: "environment" }, 
            qrConfig,
            (decodedText, decodedResult) => {
                if (isSubmitted) return;
                isSubmitted = true;

                let rawData = decodedText.trim();
                let assetCode = rawData;
                
                if (rawData.includes("?scan=")) {
                    assetCode = rawData.split("?scan=").pop().split("&")[0].trim();
                }

                document.getElementById("qr-result").innerHTML = "🔄 กำลังดึงข้อมูลรหัส: <span style='color:#1d4ed8;'>" + assetCode + "</span>...";

                html5QrCode.stop().then(() => {
                    const parentDoc = window.parent.document;
                    const targetInput = parentDoc.querySelector('input[aria-label="กรอกหมายเลขครุภัณฑ์ เพื่อค้นหา"]');
                    
                    if (targetInput) {
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                        nativeInputValueSetter.call(targetInput, assetCode);
                        
                        targetInput.dispatchEvent(new Event('input', { bubbles: true }));
                        targetInput.dispatchEvent(new Event('change', { bubbles: true }));
                        targetInput.focus();

                        setTimeout(() => {
                            const enterEvent = new KeyboardEvent('keydown', {
                                bubbles: true, cancelable: true, keyCode: 13, key: 'Enter', code: 'Enter'
                            });
                            targetInput.dispatchEvent(enterEvent);

                            const buttons = parentDoc.querySelectorAll('button');
                            for (let btn of buttons) {
                                if (btn.innerText.includes("🔍 ค้นหา")) {
                                    btn.click();
                                    break;
                                }
                            }
                        }, 150);
                    }
                }).catch(err => {});
            },
            (errorMessage) => {}
        ).catch((err) => {
            document.getElementById("qr-result").style.color = "#dc2626";
            document.getElementById("qr-result").innerText = "⚠️ ไม่สามารถเปิดกล้องได้ (โปรดอนุญาตให้ใช้กล้องในเบราว์เซอร์)";
        });
    </script>
    """
    return components.html(scanner_html, height=340)


# =========================================================
# --- 🔐 ระบบ Login & จัดการสิทธิ์หน่วยงาน ---
# =========================================================
if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False
if "current_agency" not in st.session_state:
    st.session_state.current_agency = ""
if "current_agency_name" not in st.session_state:
    st.session_state.current_agency_name = ""
if "current_password" not in st.session_state:
    st.session_state.current_password = ""

if not st.session_state.is_logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 1.6, 1])

    with col_l2:
        st.markdown("<div style='text-align: center;'><h2 style='color: #1e3a8a;'>🏛️ เข้าสู่ระบบตรวจครุภัณฑ์</h2><p style='color: #64748b;'>ระบบตรวจนับครุภัณฑ์ประจำปี (Cloud Version)</p></div>", unsafe_allow_html=True)

        with st.container(border=True):
            with st.form("login_form"):
                login_code = st.text_input("👤 รหัสหน่วยงาน (Agency Code)", placeholder="เช่น cgduthai หรือ singloma01")
                login_pass = st.text_input("🔑 รหัสผ่าน (Password)", type="password")
                submit_login = st.form_submit_button("🚀 เข้าสู่ระบบ", type="primary", use_container_width=True)

                if submit_login:
                    code_in = login_code.strip().lower()
                    pass_in = login_pass.strip()

                    if code_in == "cgduthai" and pass_in == "admin1234":
                        st.session_state.is_logged_in = True
                        st.session_state.current_agency = "cgduthai"
                        st.session_state.current_agency_name = "สำนักงานคลังจังหวัดอุทัยธานี"
                        st.session_state.current_password = pass_in
                        st.rerun()
                    elif not code_in or not pass_in:
                        st.error("⚠️ กรุณากรอกรหัสหน่วยงานและรหัสผ่านให้ครบถ้วน")
                    else:
                        if supabase:
                            try:
                                res = supabase.table("agencies").select("agency_code, agency_name, password").eq("agency_code", code_in).execute()
                                if res.data:
                                    matched = res.data[0]
                                    if str(matched.get("password", "")).strip() == pass_in:
                                        st.session_state.is_logged_in = True
                                        st.session_state.current_agency = matched["agency_code"]
                                        st.session_state.current_agency_name = matched["agency_name"]
                                        st.session_state.current_password = pass_in
                                        st.rerun()
                                    else:
                                        st.error("❌ รหัสผ่านไม่ถูกต้อง")
                                else:
                                    st.error("❌ ไม่พบรหัสหน่วยงานนี้ในระบบ")
                            except Exception as e:
                                st.error(f"⚠️ ข้อผิดพลาดเชื่อมต่อฐานข้อมูล: {e}")

        st.markdown("<hr style='margin: 18px 0px;'>", unsafe_allow_html=True)
        with st.expander("➕ ยังไม่มีหน่วยงาน? คลิกที่นี่เพื่อลงทะเบียน"):
            with st.form("register_agency_form_public"):
                new_code = st.text_input("รหัสหน่วยงาน (ภาษาอังกฤษตัวพิมพ์เล็กติดกัน เช่น school01)")
                new_name = st.text_input("ชื่อหน่วยงานเต็ม")
                new_email = st.text_input("อีเมลผู้ดูแลระบบ")
                new_pass = st.text_input("กำหนดรหัสผ่าน", type="password")
                reg_btn = st.form_submit_button("ลงทะเบียนหน่วยงานใหม่", use_container_width=True)

                if reg_btn:
                    if not new_code or not new_name or not new_pass:
                        st.error("กรุณากรอกรหัสหน่วยงาน ชื่อ และรหัสผ่าน")
                    else:
                        try:
                            supabase.table("agencies").insert({
                                "agency_code": new_code.strip().lower(),
                                "agency_name": new_name.strip(),
                                "admin_email": new_email.strip() if new_email else "-",
                                "password": new_pass.strip()
                            }).execute()
                            st.success("🎉 ลงทะเบียนสำเร็จ! สามารถนำรหัสและรหัสผ่านไปเข้าสู่ระบบได้ทันที")
                        except Exception as e:
                            st.error(f"⚠️ รหัสหน่วยงานซ้ำ หรือเกิดข้อผิดพลาด: {e}")
    st.stop()


# =========================================================
# --- 🖥️ หน้าจอส่วนหลัก (Main UI) ---
# =========================================================
active_agency = st.session_state.current_agency

with st.sidebar:
    st.markdown("### 👤 ข้อมูลผู้ใช้งาน")
    st.info(f"**หน่วยงาน:** {st.session_state.current_agency_name}\n\n**รหัส:** `{active_agency}`")

    if st.button("🚪 ออกจากระบบ (Logout)", type="secondary", use_container_width=True):
        st.session_state.is_logged_in = False
        st.session_state.current_agency = ""
        st.session_state.current_agency_name = ""
        st.session_state.current_password = ""
        st.rerun()

# หัวข้อโปรเจกต์
st.markdown("<div class='app-header'>🏛️ ระบบตรวจครุภัณฑ์ (Secure Cloud Version)</div>", unsafe_allow_html=True)

st.markdown(f"""
    <div class='agency-banner'>
        <span>📌 กำลังปฏิบัติงานในนาม: <b>{st.session_state.current_agency_name}</b> (รหัส: {active_agency})</span>
        <span style='font-size: 13px; background: rgba(255,255,255,0.25); padding: 4px 10px; border-radius: 6px;'>Secure Multi-Tenant</span>
    </div>
""", unsafe_allow_html=True)

available_years = get_agency_years(active_agency)

# 🔼 แถวควบคุมด้านบน: เลือกปีงบประมาณ + ปุ่มนำเข้าไฟล์/นำออกไฟล์ Excel
col_year_top, col_upload_top = st.columns([2.5, 4.5])

with col_year_top:
    selected_fiscal_year = st.selectbox(
        "📅 เลือกปีงบประมาณที่ต้องการดูข้อมูล",
        options=available_years,
        key="global_fiscal_year_select"
    )
    year_key = selected_fiscal_year

with col_upload_top:
    st.markdown("<div style='margin-top: 27px;'></div>", unsafe_allow_html=True)
    with st.popover("📤 นำเข้าไฟล์/นำออกไฟล์ Excel บัญชีครุภัณฑ์", use_container_width=True):
        st.markdown(f"##### 📤 นำเข้าข้อมูลสำหรับ: **{st.session_state.current_agency_name}**")
        st.caption("อัปโหลดไฟล์ Excel (.xlsx, .xls) ระบบจะพยายามอ่านปีงบประมาณจากชื่อไฟล์ให้อัตโนมัติ")
        
        top_excel_upload = st.file_uploader("เลือกไฟล์ Excel", type=["xlsx", "xls"], key="top_uploader_key")
        
        if top_excel_upload:
            try:
                year_match = re.search(r'(25\d{2})', top_excel_upload.name)
                default_year = year_match.group(1) if year_match else (year_key if year_key != "รอการอัปโหลดไฟล์" else "2570")
                upload_year = st.text_input("📌 ระบุปีงบประมาณสำหรับไฟล์นี้ (เช่น 2570)", value=default_year)

                raw_excel = pd.read_excel(top_excel_upload, header=None)
                
                header_idx = None
                for idx in range(min(15, len(raw_excel))):
                    row_vals = [str(v).strip() for v in raw_excel.iloc[idx].values if pd.notna(v)]
                    if any(any(k in val for k in ['หมายเลขครุภัณฑ์', 'รหัสครุภัณฑ์', 'เลขครุภัณฑ์']) for val in row_vals):
                        header_idx = idx
                        break
                    elif any('รายการ' in val for val in row_vals) and any('รหัส' in val or 'เลข' in val for val in row_vals):
                        header_idx = idx
                        break
                
                if header_idx is None:
                    header_idx = header_row if len(raw_excel) > header_row else 0
                
                p_df = raw_excel.iloc[header_idx + 1:].copy().reset_index(drop=True)
                p_df.columns = [str(c).strip() for c in raw_excel.iloc[header_idx].values]
                p_df = p_df.dropna(how='all').reset_index(drop=True)

                code_cols = [c for c in p_df.columns if any(k in str(c) for k in ['หมายเลขครุภัณฑ์', 'รหัสครุภัณฑ์', 'เลขครุภัณฑ์', 'รหัส', 'เลข'])]
                m_code_col = code_cols[0] if code_cols else p_df.columns[0]
                
                st.success(f"🎯 พบคอลัมน์รหัส: **'{m_code_col}'** (ตรวจพบ {len(p_df)} รายการ)")

                if st.button("🚀 ยืนยันบันทึกขึ้น Cloud ทันที", type="primary", use_container_width=True, key="btn_confirm_upload_top"):
                    upload_dict = {}
                    clean_upload_year = str(upload_year).strip()
                    for _, r in p_df.iterrows():
                        c_val = str(r[m_code_col]).strip()
                        if not c_val or c_val in ['nan', 'None', '-'] or not re.search(r'\d', c_val):
                            continue
                        r_data = {str(k): ('' if pd.isna(v) else str(v).strip()) for k, v in r.items()}
                        upload_dict[c_val] = {
                            "agency_id": active_agency,
                            "fiscal_year": clean_upload_year,
                            "asset_code": c_val,
                            "row_data": r_data
                        }

                    upload_rows = list(upload_dict.values())
                    if upload_rows and supabase:
                        batch_size = 150
                        for i in range(0, len(upload_rows), batch_size):
                            supabase.table("agency_assets").upsert(
                                upload_rows[i:i + batch_size],
                                on_conflict="agency_id,fiscal_year,asset_code"
                            ).execute()

                        get_agency_years.clear()
                        get_shared_data.clear()
                        st.session_state.cloud_save_success_toast = True
                        st.rerun()
                    else:
                        st.error("⚠️ ไม่พบข้อมูลรหัสครุภัณฑ์ที่ถูกต้องในไฟล์")
            except Exception as ex:
                st.error(f"เกิดข้อผิดพลาด: {ex}")
        
        st.markdown("<hr style='margin: 15px 0px;'>", unsafe_allow_html=True)
        st.markdown("🧨 **พื้นที่อันตราย (ล้างข้อมูลทั้งปีงบประมาณ)**")
        st.caption(f"หากอัปโหลดไฟล์ผิด สามารถกดลบข้อมูลของปี **{year_key}** ทิ้งเพื่ออัปโหลดใหม่ได้")
        
        confirm_pass = st.text_input(f"กรอกรหัสผ่านของหน่วยงานเพื่อยืนยันการลบข้อมูลปี {year_key}", type="password", key="confirm_delete_pass")
        
        if st.button(f"🗑️ ลบข้อมูลครุภัณฑ์ปี {year_key} ทิ้งทั้งหมด", type="secondary", use_container_width=True):
            if confirm_pass:
                try:
                    is_valid_pwd = False
                    if active_agency == "cgduthai" and confirm_pass.strip() == "admin1234":
                        is_valid_pwd = True
                    else:
                        res = supabase.table("agencies").select("password").eq("agency_code", active_agency).execute()
                        if res.data and str(res.data[0].get("password", "")).strip() == confirm_pass.strip():
                            is_valid_pwd = True

                    if is_valid_pwd:
                        if year_key != "รอการอัปโหลดไฟล์":
                            supabase.table("agency_assets").delete().eq("agency_id", active_agency).eq("fiscal_year", year_key).execute()
                            supabase.table("core_assetauditrecord").delete().eq("agency_id", active_agency).eq("fiscal_year", year_key).execute()
                            
                            get_agency_years.clear()
                            get_shared_data.clear()
                            
                            st.session_state.cloud_delete_success_toast = True
                            st.rerun()
                    else:
                        st.error("❌ รหัสผ่านไม่ถูกต้อง ไม่สามารถลบข้อมูลได้")
                except Exception as e:
                    st.error(f"⚠️ เกิดข้อผิดพลาดในการตรวจสอบรหัสผ่าน: {e}")
            else:
                st.warning("⚠️ กรุณากรอกรหัสผ่านก่อนกดยืนยันการลบ")

st.markdown("<hr style='margin: 6px 0px 12px 0px;'>", unsafe_allow_html=True)

# --- 💬 แสดงป๊อปอัพแจ้งเตือนสถานะ ---
if "cloud_save_success_toast" in st.session_state:
    show_1sec_popup("✅ บันทึกข้อมูลขึ้น cloud แล้ว", is_success=True)
    del st.session_state.cloud_save_success_toast

if "cloud_delete_success_toast" in st.session_state:
    show_1sec_popup("🗑️ ลบข้อมูลออกจาก cloud แล้ว", is_success=True)
    del st.session_state.cloud_delete_success_toast

if "flash_success_msg" in st.session_state:
    st.toast(st.session_state.flash_success_msg, icon="✅")
    st.success(st.session_state.flash_success_msg)
    del st.session_state.flash_success_msg

# --- 📷 รองรับการสแกน QR Code จาก URL Query Params ---
scanned_param = st.query_params.get("scan", "")
if scanned_param:
    clean_scan = str(scanned_param).strip()
    if "?scan=" in clean_scan:
        clean_scan = clean_scan.split("?scan=").pop().split("&")[0].strip()
    st.session_state.scanned_asset_box = clean_scan
    st.session_state.active_search_query = clean_scan
    st.session_state.open_scanner = False
    st.session_state.trigger_popup_check = True
    st.session_state.nav_menu_radio = "📝 ตรวจครุภัณฑ์/บันทึกผลการตรวจ/แก้ไขผลการตรวจ"
    st.query_params.clear()

# --- 📦 โหลดข้อมูลครุภัณฑ์ ---
df, target_column, current_year_key = get_shared_data(selected_fiscal_year, active_agency)

if df is None:
    st.error(f"⚠️ ไม่พบไฟล์ข้อมูลของ **{selected_fiscal_year}** บนระบบ")
else:
    required_system_cols = ['สภาพครุภัณฑ์', 'สถานะการตรวจ', 'หมายเหตุ', 'ผู้ตรวจ', 'วันเดือนปี เวลา ที่ทำการตรวจสอบ']
    for c in required_system_cols:
        if c not in df.columns:
            df[c] = 'ยังไม่ตรวจ' if c == 'สถานะการตรวจ' else '-'

    if target_column not in df.columns:
        df[target_column] = '-'

    valid_mask = df[target_column].apply(is_valid_asset_code)
    valid_df = df[valid_mask]
    total_items = len(valid_df)

    if not valid_df.empty:
        checked_items = len(valid_df[valid_df['สถานะการตรวจ'] == 'ตรวจแล้ว'])
        unchecked_items = len(valid_df[valid_df['สถานะการตรวจ'] == 'ยังไม่ตรวจ'])
        normal_count = len(valid_df[(valid_df['สถานะการตรวจ'] == 'ตรวจแล้ว') & (valid_df['สภาพครุภัณฑ์'] == 'ปกติ')])
        damaged_count = len(valid_df[(valid_df['สถานะการตรวจ'] == 'ตรวจแล้ว') & (valid_df['สภาพครุภัณฑ์'] == 'ชำรุด/เสียหาย')])
        obsolete_count = len(valid_df[(valid_df['สถานะการตรวจ'] == 'ตรวจแล้ว') & (valid_df['สภาพครุภัณฑ์'] == 'หมดความจำเป็น')])
    else:
        checked_items, unchecked_items, normal_count, damaged_count, obsolete_count = 0, 0, 0, 0, 0

    progress_pct = (checked_items / total_items) * 100 if total_items > 0 else 0.0
    bar_width = max(progress_pct, 1.5) if checked_items > 0 else 0.0

    st.markdown(
        f"**ความคืบหน้าการตรวจสอบภาพรวม ({selected_fiscal_year}): {progress_pct:.2f}%** (ตรวจแล้ว {checked_items} จาก {total_items} รายการ)",
        unsafe_allow_html=True
    )
    st.markdown(
        f"""
        <div class="progress-wrapper">
            <div class="progress-fill" style="width: {bar_width}%;"></div>
        </div>
        """,
        unsafe_allow_html=True
    )

    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    m1.metric("📦 ทั้งหมด", total_items)
    m2.metric("✔️ ตรวจแล้ว", checked_items)
    m3.metric("⏳ ยังไม่ตรวจ", unchecked_items)
    m4.metric("✅ สภาพปกติ", normal_count)
    m5.metric("⚠️ ชำรุด/เสียหาย", damaged_count)
    m6.metric("📦 หมดความจำเป็น", obsolete_count)

    condition_options = [
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
        "แปรสภาพหรือทำลาย"
    ]
    other_conditions = condition_options[3:]

    with m7:
        selected_top_other = st.selectbox(
            "📋 สภาพอื่นๆ", 
            ["เลือกดูสภาพ..."] + other_conditions,
            key="top_other_metric_dropdown",
            label_visibility="visible"
        )
        if selected_top_other != "เลือกดูสภาพ...":
            other_count = len(valid_df[(valid_df['สถานะการตรวจ'] == 'ตรวจแล้ว') & (valid_df['สภาพครุภัณฑ์'] == selected_top_other)])
            st.markdown(f"<div style='font-size: 15px; font-weight: 700; color: #1d4ed8; text-align: center; margin-top: -6px;'>จำนวน: {other_count} ราย</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='font-size: 12px; color: #64748b; text-align: center; margin-top: -8px;'>เลือกดูจำนวน</div>", unsafe_allow_html=True)

    if total_items == 0:
        st.info("ℹ️ หน่วยงานของคุณยังไม่มีข้อมูลครุภัณฑ์ในระบบ กรุณากดปุ่ม **'📤 นำเข้าไฟล์/นำออกไฟล์ Excel บัญชีครุภัณฑ์'** ด้านบน เพื่อนำเข้าไฟล์ครุภัณฑ์ตั้งต้นครับ")

    st.markdown("<hr style='margin: 12px 0px;'>", unsafe_allow_html=True)

    m1_name = "🔍 ค้นหา/โหมดแก้ไขรายละเอียด"
    m2_name = "📝 ตรวจครุภัณฑ์/บันทึกผลการตรวจ/แก้ไขผลการตรวจ"
    m3_name = "🏷️ สร้าง QR Code"
    m4_name = "📥 ส่งออกรายงาน Excel"

    menu_options = [m1_name, m2_name, m3_name, m4_name]

    selected_menu = st.radio(
        "เลือกเมนูการทำงาน:",
        options=menu_options,
        horizontal=True,
        label_visibility="collapsed",
        key="nav_menu_radio"
    )

    st.markdown("<hr style='margin: 10px 0px 16px 0px;'>", unsafe_allow_html=True)
    
    status_options = [
        "ตรวจแล้ว",
        "ยังไม่ตรวจ"
    ]

    # ================= MENU 1: ค้นหา / โหมดแก้ไขรายละเอียด =================
    if selected_menu == m1_name:
        st.subheader(f"🔍 ค้นหาข้อมูลครุภัณฑ์ ({selected_fiscal_year})")
        
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            search_query = st.text_input("พิมพ์ค้นหา:", placeholder="ชื่อ, หมายเลขครุภัณฑ์, สถานที่...", key="search_main_1")
        with col_s2:
            condition_filter = st.selectbox("กรองสภาพครุภัณฑ์", ["ทั้งหมด"] + condition_options, key="filter_cond_main_1")
        with col_s3:
            status_filter = st.selectbox("กรองสถานะการตรวจ", ["ทั้งหมด"] + status_options, key="filter_main_1")
        with col_s4:
            inspector_filter = st.text_input("กรองผู้ตรวจ:", placeholder="ชื่อผู้ตรวจสอบ...", key="filter_inspector_main")
        
        display_df = df[valid_mask].copy()
        
        if selected_top_other != "เลือกดูสภาพ...":
            display_df = display_df[display_df['สภาพครุภัณฑ์'] == selected_top_other]

        if status_filter != "ทั้งหมด":
            display_df = display_df[display_df['สถานะการตรวจ'] == status_filter]
        if condition_filter != "ทั้งหมด":
            display_df = display_df[display_df['สภาพครุภัณฑ์'] == condition_filter]
        if inspector_filter:
            display_df = display_df[display_df['ผู้ตรวจ'].astype(str).str.contains(inspector_filter, case=False, na=False)]
        if search_query:
            display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]

        st.dataframe(display_df, use_container_width=True)

        # ปุ่มดาวน์โหลดรายการที่กรองแสดงอยู่ในตาราง
        col_dl_btn, col_space = st.columns([1.2, 3.8])
        with col_dl_btn:
            filtered_buffer = BytesIO()
            display_df.to_excel(filtered_buffer, index=False)
            filtered_data = filtered_buffer.getvalue()
            
            thai_now = datetime.utcnow() + timedelta(hours=7)
            st.download_button(
                label="📥 ดาวน์โหลดรายการที่แสดงนี้ (Excel)",
                data=filtered_data,
                file_name=f"รายงานครุภัณฑ์_{active_agency}_{selected_fiscal_year}_{thai_now.strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.markdown("<hr style='margin: 16px 0px;'>", unsafe_allow_html=True)
        enable_admin_tools = st.checkbox("⚙️ เปิดใช้งานโหมด: แก้ไขรายละเอียดครุภัณฑ์ / เพิ่มรายการใหม่ (สำหรับผู้ดูแลระบบ)", value=False)
        
        if enable_admin_tools:
            st.markdown(f"### 🛠️ แก้ไขรายละเอียดครุภัณฑ์ ({selected_fiscal_year})")
            
            with st.container(border=True):
                mode_select = st.radio(
                    "เลือกโหมดการทำงาน:",
                    ["✏️ แก้ไขข้อมูลครุภัณฑ์เดิม", "➕ เพิ่มรายการครุภัณฑ์ใหม่ขึ้น Cloud"],
                    horizontal=True
                )
                
                non_editable_audit_cols = {'สภาพครุภัณฑ์', 'สถานะการตรวจ', 'ผู้ตรวจ', 'วันเดือนปี เวลา ที่ทำการตรวจสอบ'}
                editable_cols = [c for c in df.columns if c not in non_editable_audit_cols and c != target_column]
                
                if 'หมายเหตุ' not in editable_cols and 'หมายเหตุ' in df.columns:
                    editable_cols.append('หมายเหตุ')

                if mode_select == "✏️ แก้ไขข้อมูลครุภัณฑ์เดิม":
                    asset_list_for_edit = df[valid_mask][target_column].tolist()
                    if not asset_list_for_edit:
                        st.warning("⚠️ ยังไม่มีรายการครุภัณฑ์ให้แก้ไข")
                    else:
                        edit_target = st.selectbox(
                            f"เลือกหมายเลขครุภัณฑ์ที่ต้องการแก้ไขข้อมูล ({target_column})",
                            options=asset_list_for_edit,
                            key="cloud_edit_item_select"
                        )
                        target_row = df[df[target_column].astype(str).str.strip() == str(edit_target).strip()].iloc[0]
                        
                        with st.form("cloud_edit_asset_form"):
                            st.caption(f"พิมพ์แก้ไขข้อมูลสำหรับ {selected_fiscal_year} แล้วกดปุ่มบันทึกด้านล่าง")
                            updated_values = {}
                            cols_ui = st.columns(3)
                            
                            for idx, col_name in enumerate(editable_cols):
                                with cols_ui[idx % 3]:
                                    current_val = str(target_row.get(col_name, '-'))
                                    if current_val in ['nan', 'None']:
                                        current_val = '-'
                                        
                                    updated_values[col_name] = st.text_input(
                                        col_name,
                                        value=current_val,
                                        key=f"edit_field_{col_name}_{edit_target}"
                                    )
                            
                            col_btn_save, col_btn_del = st.columns(2)
                            with col_btn_save:
                                save_edit_cloud = st.form_submit_button("☁️ บันทึกการแก้ไขข้อมูลนี้ขึ้น Cloud", type="primary", use_container_width=True)
                            with col_btn_del:
                                delete_cloud_btn = st.form_submit_button("🗑️ ลบรายการนี้ออกจาก Cloud", type="secondary", use_container_width=True)

                            if save_edit_cloud:
                                note_val = updated_values.get('หมายเหตุ', '-')
                                if not note_val or note_val in ['nan', 'None']:
                                    note_val = '-'
                                updated_values['หมายเหตุ_ข้อมูลหลัก'] = note_val
                                
                                ok = save_progress_to_supabase(
                                    asset_code=edit_target,
                                    condition=target_row['สภาพครุภัณฑ์'],
                                    status=target_row['สถานะการตรวจ'],
                                    note=note_val,
                                    inspector=target_row['ผู้ตรวจ'],
                                    timestamp=target_row['วันเดือนปี เวลา ที่ทำการตรวจสอบ'],
                                    fiscal_year=current_year_key,
                                    agency_id=active_agency,
                                    extra_dict=updated_values
                                )
                                if ok:
                                    get_shared_data.clear()
                                    st.session_state.cloud_save_success_toast = True
                                    st.rerun()

                            if delete_cloud_btn:
                                ok = delete_asset_from_supabase(edit_target, current_year_key, active_agency)
                                if ok:
                                    get_shared_data.clear()
                                    st.session_state.cloud_delete_success_toast = True
                                    st.rerun()

                else:
                    with st.form("cloud_add_asset_form"):
                        st.caption(f"กรอกหมายเลขครุภัณฑ์ใหม่สำหรับ {selected_fiscal_year}")
                        new_code = st.text_input(f"🌟 {target_column} (จำเป็นต้องกรอกและมีตัวเลข)")
                        
                        new_values = {}
                        cols_ui = st.columns(3)
                        
                        for idx, col_name in enumerate(editable_cols):
                            with cols_ui[idx % 3]:
                                new_values[col_name] = st.text_input(col_name, value="-", key=f"new_col_{idx}")

                        save_new_cloud = st.form_submit_button("➕ เพิ่มรายการใหม่และบันทึกขึ้น Cloud", type="primary", use_container_width=True)
                        if save_new_cloud:
                            if not is_valid_asset_code(new_code):
                                st.error(f"⚠️ กรุณากรอก '{target_column}' ให้ถูกต้อง")
                            elif str(new_code).strip() in df[target_column].astype(str).str.strip().values:
                                st.warning("⚠️ หมายเลขครุภัณฑ์นี้มีอยู่ในระบบแล้ว")
                            else:
                                note_val = new_values.get('หมายเหตุ', '-')
                                if not note_val or note_val in ['nan', 'None']:
                                    note_val = '-'
                                new_values['หมายเหตุ_ข้อมูลหลัก'] = note_val
                                target_year_to_save = current_year_key if current_year_key != "รอการอัปโหลดไฟล์" else "2570"
                                ok = save_progress_to_supabase(
                                    asset_code=new_code.strip(),
                                    condition="-",
                                    status="ยังไม่ตรวจ",
                                    note=note_val,
                                    inspector="-",
                                    timestamp="-",
                                    fiscal_year=target_year_to_save,
                                    agency_id=active_agency,
                                    extra_dict=new_values
                                )
                                if ok:
                                    get_agency_years.clear()
                                    get_shared_data.clear()
                                    st.session_state.cloud_save_success_toast = True
                                    st.rerun()

    # ================= MENU 2: ตรวจครุภัณฑ์ / บันทึกผลการตรวจ =================
    elif selected_menu == m2_name:
        st.subheader(f"📝 ตรวจครุภัณฑ์ / บันทึกผลการตรวจ ({selected_fiscal_year})")
        st.write("ใช้สำหรับสแกน QR Code หรือกรอกหมายเลขครุภัณฑ์เพื่อค้นหาและบันทึกผลการตรวจ")
        
        def on_asset_input_change():
            raw_val = st.session_state.get("scanned_asset_box", "").strip()
            if raw_val:
                clean_code = raw_val.split("?scan=").pop().split("&")[0].strip() if "?scan=" in raw_val else raw_val
                st.session_state.scanned_asset_box = clean_code
                st.session_state.active_search_query = clean_code
                st.session_state.open_scanner = False
                st.session_state.trigger_popup_check = True

        left_box, right_box = st.columns([6, 6])
        
        with left_box:
            with st.container(border=True):
                st.markdown("##### 🔎 ค้นหาหรือสแกน QR Code")
                
                if "open_scanner" not in st.session_state:
                    st.session_state.open_scanner = False
                
                btn_label = "❌ ปิดกล้องสแกน QR Code" if st.session_state.open_scanner else "📷 กดปุ่มสแกน QR Code หมายเลขพัสดุ"
                if st.button(btn_label, use_container_width=True, type="primary" if not st.session_state.open_scanner else "secondary"):
                    st.session_state.open_scanner = not st.session_state.open_scanner
                    st.rerun()
                
                if st.session_state.open_scanner:
                    render_auto_submit_qr_scanner()

                scanned_code_input = st.text_input(
                    "กรอกหมายเลขครุภัณฑ์ เพื่อค้นหา",
                    key="scanned_asset_box",
                    placeholder="สแกน QR Code หรือพิมพ์หมายเลข...",
                    on_change=on_asset_input_change
                )
                
                col_btn_mid, col_space_mid = st.columns([1.5, 2.5])
                with col_btn_mid:
                    search_triggered_mid = st.button("🔍 ค้นหา", key="btn_search_mid", type="primary", use_container_width=True)

        if search_triggered_mid and scanned_code_input.strip():
            raw_val = scanned_code_input.strip()
            clean_code = raw_val.split("?scan=").pop().split("&")[0].strip() if "?scan=" in raw_val else raw_val
            st.session_state.active_search_query = clean_code
            st.session_state.open_scanner = False
            st.session_state.trigger_popup_check = True

        current_query = st.session_state.get("active_search_query", "")

        if current_query:
            search_term = current_query.split("?scan=").pop().split("&")[0].strip() if "?scan=" in current_query else current_query

            matched_mob = valid_df[
                valid_df[target_column].astype(str).str.strip().str.contains(search_term, case=False, na=False, regex=False)
            ]
            if matched_mob.empty:
                matched_mob = valid_df[
                    valid_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False, regex=False)).any(axis=1)
                ]

            if st.session_state.get("trigger_popup_check", False):
                st.session_state.trigger_popup_check = False
                if not matched_mob.empty:
                    show_1sec_popup("✅ ค้นพบข้อมูล", is_success=True)
                else:
                    show_1sec_popup("❌ ไม่พบข้อมูล/QR Code ไม่ถูกต้อง", is_success=False)

            if not matched_mob.empty:
                st.success(f"🎯 พบข้อมูลครุภัณฑ์ที่ตรงกับรหัส/คำค้นหา: {len(matched_mob)} รายการ")
                st.dataframe(matched_mob, use_container_width=True)
                
                target_row_data = matched_mob.iloc[0]
                mob_target = str(target_row_data[target_column]).strip()
                
                st.markdown(f"### 📝 บันทึก / แก้ไขผลการตรวจสำหรับรหัส: <span style='color: #1d4ed8;'>{mob_target}</span>", unsafe_allow_html=True)
                
                with st.container(border=True):
                    col_info_badge, col_info_details = st.columns([1.5, 1.5])
                    with col_info_badge:
                        st.markdown(f"<div style='font-size: 14px; font-weight: 600; margin-bottom: 4px; color: #31333F;'>สถานะปัจจุบัน ({selected_fiscal_year})</div>", unsafe_allow_html=True)
                        render_status_badge(
                            target_row_data['สถานะการตรวจ'],
                            target_row_data['สภาพครุภัณฑ์'],
                            target_row_data['ผู้ตรวจ']
                        )
                    with col_info_details:
                        st.markdown(f"**ชื่อรายการ:** {target_row_data.get('รายการ', '-')}")
                        st.markdown(f"**สถานที่/อยู่ที่:** {target_row_data.get('อยู่ที่', '-')}")

                    cur_cond = str(target_row_data['สภาพครุภัณฑ์']).strip()
                    default_cond_idx = condition_options.index(cur_cond) if cur_cond in condition_options else 0
                    
                    cur_status = str(target_row_data['สถานะการตรวจ']).strip()
                    default_status_idx = status_options.index(cur_status) if cur_status in status_options else 0
                    
                    cur_note = str(target_row_data['หมายเหตุ']).strip()
                    if cur_note in ['-', 'nan', 'None']:
                        cur_note = ""
                        
                    cur_insp = str(target_row_data['ผู้ตรวจ']).strip()
                    if cur_insp in ['-', 'nan', 'None']:
                        cur_insp = ""

                    with st.form(key=f"audit_form_{mob_target}", border=False):
                        mc1, mc2, mc3, mc4 = st.columns(4)
                        with mc1:
                            mob_condition = st.selectbox("1. สภาพครุภัณฑ์", condition_options, index=default_cond_idx)
                        with mc2:
                            mob_status = st.selectbox("2. สถานะการตรวจ", status_options, index=default_status_idx)
                        with mc3:
                            mob_note = st.text_input("หมายเหตุ (รายละเอียดเพิ่มเติม)", value=cur_note)
                        with mc4:
                            mob_inspector = st.text_input("3. ผู้ตรวจ (ชื่อผู้ตรวจสอบ/กรรมการ)", value=cur_insp)
                        
                        m_btn_col, m_save_status_col = st.columns([1.2, 1.8])
                        with m_btn_col:
                            mob_submit = st.form_submit_button(
                                label="💾 บันทึกผลการตรวจทันที",
                                type="primary",
                                use_container_width=True
                            )
                        with m_save_status_col:
                            render_save_status_badge(
                                target_row_data['สถานะการตรวจ'],
                                target_row_data['วันเดือนปี เวลา ที่ทำการตรวจสอบ']
                            )
                        
                        if mob_submit:
                            thai_time = datetime.utcnow() + timedelta(hours=7)
                            current_time = thai_time.strftime("%d/%m/%Y %H:%M:%S")
                            
                            if mob_status == "ยังไม่ตรวจ":
                                m_condition = '-'
                                m_status_val = 'ยังไม่ตรวจ'
                                m_note_val = mob_note.strip() if mob_note.strip() else '-'
                                m_inspector_val = '-'
                                m_time_val = '-'
                            else:
                                m_condition = mob_condition
                                m_status_val = mob_status
                                m_note_val = mob_note.strip() if mob_note.strip() else '-'
                                m_inspector_val = mob_inspector.strip() if mob_inspector.strip() else '-'
                                m_time_val = current_time
                            
                            ok = save_progress_to_supabase(
                                asset_code=mob_target,
                                condition=m_condition,
                                status=m_status_val,
                                note=m_note_val,
                                inspector=m_inspector_val,
                                timestamp=m_time_val,
                                fiscal_year=current_year_key,
                                agency_id=active_agency
                            )
                            if ok:
                                get_shared_data.clear()
                                st.session_state.open_scanner = False
                                st.session_state.flash_success_msg = f"✅ บันทึกผลการตรวจครุภัณฑ์ {selected_fiscal_year} สำเร็จเรียบร้อย!"
                                st.rerun()
            else:
                st.warning(f"⚠️ ไม่พบข้อมูลครุภัณฑ์รหัส '{search_term}' ในระบบ (QR Code อาจไม่ถูกต้องหรือเป็นข้อมูลจากแหล่งอื่น)")

    # ================= MENU 3: สร้าง QR Code =================
    elif selected_menu == m3_name:
        st.subheader(f"🏷️ ระบบสร้าง QR Code ({selected_fiscal_year})")
        qr_options_list = df[valid_mask][target_column].tolist() if not df.empty else []
        selected_qr_item = st.selectbox("เลือกหมายเลขครุภัณฑ์ที่ต้องการสร้าง QR", options=qr_options_list, key="gen_qr_tab")
        
        if selected_qr_item:
            base_url = "https://asset-audit-app-bbywyvjvpavzrkh8skqrmf.streamlit.app/"
            qr_payload = f"{base_url}?scan={selected_qr_item}"
            
            qr = qrcode.QRCode(version=1, box_size=12, border=2)
            qr.add_data(qr_payload)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
            
            qr_width, qr_height = qr_img.size
            padding_bottom = 28  
            new_img = Image.new('RGB', (qr_width, qr_height + padding_bottom), 'white')
            new_img.paste(qr_img, (0, 0))
            
            draw = ImageDraw.Draw(new_img)
            text_to_print = str(selected_qr_item)
            
            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except Exception:
                try:
                    font = ImageFont.truetype("DejaVuSans.ttf", 20)
                except Exception:
                    font = ImageFont.load_default()
                
            bbox = draw.textbbox((0, 0), text_to_print, font=font)
            text_width = bbox[2] - bbox[0]
            
            text_x = (qr_width - text_width) / 2
            text_y = qr_height - 1  
            
            draw.text((text_x, text_y), text_to_print, fill="black", font=font)
            
            buf = BytesIO()
            new_img.save(buf, format="PNG")
            byte_im = buf.getvalue()
            
            st.image(byte_im, caption=f"ป้าย QR Code: {selected_qr_item}", width=260)
            st.download_button(
                label=f"📥 ดาวน์โหลดรูปป้าย QR Code ({selected_qr_item})",
                data=byte_im,
                file_name=f"QRCode_Label_{selected_qr_item}.png",
                mime="image/png"
            )

    # ================= MENU 4: ส่งออกรายงาน Excel =================
    elif selected_menu == m4_name:
        st.subheader(f"📥 ดาวน์โหลดรายงานสรุปผลการตรวจสอบ ({selected_fiscal_year})")
        st.write("ข้อมูลการตรวจสอบทั้งหมดสามารถกดดาวน์โหลดเป็นไฟล์ Excel ได้ทันทีครับ")
        
        output_buffer = BytesIO()
        df[valid_mask].to_excel(output_buffer, index=False)
        output_data = output_buffer.getvalue()
        
        thai_now = datetime.utcnow() + timedelta(hours=7)
        st.download_button(
            label=f"📊 ดาวน์โหลดรายงาน Excel ของ {selected_fiscal_year}",
            data=output_data,
            file_name=f"รายงานผลการตรวจครุภัณฑ์_{active_agency}_{selected_fiscal_year}_{thai_now.strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
