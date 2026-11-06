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
    except Exception as e:
        return None
    return None

supabase: Client = init_supabase()

# ตั้งค่าหน้าเว็บให้เป็นแบบ Wide
st.set_page_config(
    page_title="ระบบตรวจครุภัณฑ์",
    page_icon="🏛️",
    layout="wide"
)

st.markdown("""
    <style>
    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 2rem;
    }
    .app-header {
        font-size: 28px;
        font-weight: 700;
        color: #1f2937;
        margin-top: 10px;
        margin-bottom: 12px;
    }
    .stAlert {
        padding: 4px 12px !important;
        margin-bottom: 0px !important;
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
    </style>
""", unsafe_allow_html=True)

# หัวข้อโปรเจกต์
st.markdown("<div class='app-header'>🏛️ ระบบตรวจครุภัณฑ์ (Cloud Version)</div>", unsafe_allow_html=True)
st.markdown("<hr style='margin: 6px 0px 12px 0px;'>", unsafe_allow_html=True)

header_row = 4

@st.cache_resource
def get_shared_data():
    if os.path.exists("default_asset.xlsx"):
        default_file = "default_asset.xlsx"
    elif os.path.exists("default_asset.xls"):
        default_file = "default_asset.xls"
    else:
        return None, None

    if default_file.endswith('.csv'):
        raw_df = pd.read_csv(default_file, header=None)
    else:
        try:
            raw_df = pd.read_excel(default_file, header=None, engine='openpyxl')
        except Exception:
            raw_df = pd.read_excel(default_file, header=None, engine='xlrd')
    
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

    audit_cols = ['สภาพครุภัณฑ์', 'สถานะการตรวจ', 'หมายเหตุ', 'ผู้ตรวจ', 'วันเดือนปี เวลา ที่ทำการตรวจสอบ']
    for col in audit_cols:
        if col not in df.columns:
            if col == 'สถานะการตรวจ':
                df[col] = 'ยังไม่ตรวจ'
            else:
                df[col] = '-'

    for col in df.columns:
        df[col] = df[col].astype(str).replace('nan', '-').replace('None', '-')

    # ดึงข้อมูลจาก Supabase Cloud (รวมถึงรายการที่เคยแก้ไขและรายการที่เพิ่มใหม่บน Cloud)
    if supabase:
        try:
            response = supabase.table("core_assetauditrecord").select("*").execute()
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
                        
                        if extra_info and 'หมายเหตุ_ข้อมูลหลัก' in extra_info:
                            df.loc[mask, 'หมายเหตุ'] = extra_info['หมายเหตุ_ข้อมูลหลัก']
                        elif actual_note != '-':
                            df.loc[mask, 'หมายเหตุ'] = actual_note

                        for col_k, val_v in extra_info.items():
                            if col_k in df.columns:
                                df.loc[mask, col_k] = str(val_v)
                    else:
                        new_r = {c: '-' for c in df.columns}
                        new_r[target_col] = code
                        new_r['สภาพครุภัณฑ์'] = str(row['condition']) if pd.notna(row['condition']) else '-'
                        new_r['สถานะการตรวจ'] = str(row['status']) if pd.notna(row['status']) else 'ยังไม่ตรวจ'
                        new_r['หมายเหตุ'] = actual_note if actual_note != '-' else '-'
                        new_r['ผู้ตรวจ'] = str(row['inspector']) if pd.notna(row['inspector']) else '-'
                        new_r['วันเดือนปี เวลา ที่ทำการตรวจสอบ'] = str(row['updated_at']) if pd.notna(row['updated_at']) else '-'
                        
                        for col_k, val_v in extra_info.items():
                            if col_k in df.columns:
                                new_r[col_k] = str(val_v)
                        new_cloud_rows.append(new_r)
                
                if new_cloud_rows:
                    df = pd.concat([df, pd.DataFrame(new_cloud_rows)], ignore_index=True)

        except Exception as e:
            st.error(f"⚠️ เกิดข้อผิดพลาดในการโหลดข้อมูลจาก Supabase: {e}")

    return df, target_col

def save_progress_to_supabase(asset_code, condition, status, note, inspector, timestamp, extra_dict=None):
    if not supabase:
        st.error("⚠️ ไม่ได้เชื่อมต่อกับ Supabase Cloud")
        return
    try:
        existing = supabase.table("core_assetauditrecord").select("note").eq("asset_code", str(asset_code)).execute()
        saved_extra = {}
        if existing.data:
            old_note = str(existing.data[0].get("note", ""))
            if "||ASSET_DATA||" in old_note:
                try:
                    saved_extra = json.loads(old_note.split("||ASSET_DATA||", 1)[1])
                except Exception:
                    saved_extra = {}
        
        if extra_dict is not None:
            saved_extra.update(extra_dict)
            
        clean_note = str(note).split("||ASSET_DATA||")[0]
        final_note = f"{clean_note}||ASSET_DATA||{json.dumps(saved_extra, ensure_ascii=False)}" if saved_extra else clean_note

        data_payload = {
            "asset_code": str(asset_code).strip(),
            "condition": condition,
            "status": status,
            "note": final_note,
            "inspector": inspector,
            "updated_at": timestamp
        }
        supabase.table("core_assetauditrecord").upsert(data_payload, on_conflict="asset_code").execute()
    except Exception as e:
        st.error(f"⚠️ ไม่สามารถบันทึกลง Supabase ได้: {e}")

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

def render_live_qr_scanner():
    scanner_html = """
    <div style="background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
        <div id="qr-reader" style="width: 100%; max-width: 400px; margin: 0 auto;"></div>
        <div id="qr-result" style="margin-top: 10px; font-family: sans-serif; font-size: 15px; color: #16a34a; font-weight: bold;">
            กำลังเปิดกล้อง... ส่องไปที่ป้าย QR Code
        </div>
        <div id="copy-container" style="margin-top: 10px; display: none;">
            <input type="text" id="scanned-code-box" readonly style="width: 70%; padding: 8px; font-size: 16px; text-align: center; border: 2px solid #22c55e; border-radius: 6px; background: #fff;" />
            <button onclick="copyToClipboard()" style="padding: 8px 14px; background: #22c55e; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; margin-left: 5px;">📋 คัดลอก</button>
        </div>
    </div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        let detectedCode = "";
        const html5QrCode = new Html5Qrcode("qr-reader");
        const qrConfig = { fps: 10, qrbox: { width: 220, height: 220 } };
        
        html5QrCode.start(
            { facingMode: "environment" }, 
            qrConfig,
            (decodedText, decodedResult) => {
                let code = decodedText.trim();
                if (code.includes("?scan=")) {
                    code = code.split("?scan=").pop().trim();
                }
                detectedCode = code;
                document.getElementById("qr-result").innerHTML = "✅ สแกนสำเร็จ: <span style='color: #1d4ed8;'>" + code + "</span>";
                
                document.getElementById("scanned-code-box").value = code;
                document.getElementById("copy-container").style.display = "block";
                
                navigator.clipboard.writeText(code).then(() => {
                    document.getElementById("qr-result").innerText = "✅ คัดลอกรหัส " + code + " ลงคลิปบอร์ดแล้ว! (นำไปวางในช่องค้นหาได้เลย)";
                }).catch(err => {});
                
                html5QrCode.stop().catch(err => {});
            },
            (errorMessage) => {}
        ).catch((err) => {
            document.getElementById("qr-result").style.color = "#dc2626";
            document.getElementById("qr-result").innerText = "⚠️ ไม่สามารถเปิดกล้องได้ (โปรดอนุญาตให้ใช้กล้องในเบราว์เซอร์)";
        });

        function copyToClipboard() {
            const copyText = document.getElementById("scanned-code-box");
            copyText.select();
            copyText.setSelectionRange(0, 99999);
            navigator.clipboard.writeText(copyText.value);
            alert("คัดลอกหมายเลข " + copyText.value + " เรียบร้อย! นำไปวางในช่องค้นหาได้เลยครับ");
        }
    </script>
    """
    return components.html(scanner_html, height=390)

df, target_column = get_shared_data()

if df is None:
    st.error("⚠️ ไม่พบไฟล์ข้อมูลกลาง 'default_asset.xlsx' หรือ 'default_asset.xls' บน GitHub โปรดอัปโหลดไฟล์ข้อมูลงสานเข้า GitHub ด้วยครับ")
else:
    def is_valid_asset_code(val):
        if pd.isna(val):
            return False
        val_str = str(val).strip()
        if val_str == '' or val_str.lower() == 'nan' or val_str == '-':
            return False
        return bool(re.search(r'\d', val_str))

    valid_mask = df[target_column].apply(is_valid_asset_code)

    valid_df = df[valid_mask]
    total_items = len(valid_df)
    checked_items = len(valid_df[valid_df['สถานะการตรวจ'] == 'ตรวจแล้ว'])
    unchecked_items = len(valid_df[valid_df['สถานะการตรวจ'] == 'ยังไม่ตรวจ'])
    
    normal_count = len(valid_df[(valid_df['สถานะการตรวจ'] == 'ตรวจแล้ว') & (valid_df['สภาพครุภัณฑ์'] == 'ปกติ')])
    damaged_count = len(valid_df[(valid_df['สถานะการตรวจ'] == 'ตรวจแล้ว') & (valid_df['สภาพครุภัณฑ์'] == 'ชำรุด/เสียหาย')])
    obsolete_count = len(valid_df[(valid_df['สถานะการตรวจ'] == 'ตรวจแล้ว') & (valid_df['สภาพครุภัณฑ์'] == 'หมดความจำเป็น')])

    progress_pct = (checked_items / total_items) * 100 if total_items > 0 else 0.0
    bar_width = max(progress_pct, 1.5) if checked_items > 0 else 0.0

    st.markdown(
        f"**ความคืบหน้าการตรวจสอบภาพรวม: {progress_pct:.2f}%** (ตรวจแล้ว {checked_items} จาก {total_items} รายการ)",
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
        "โปรดระบุสภาพ",
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
    other_conditions = condition_options[4:]

    with m7:
        selected_top_other = st.selectbox(
            "📋 สภาพอื่นๆ", 
            ["เลือกดูสภาพ..."] + other_conditions,
            key="top_other_metric_dropdown",
            label_visibility="visible"
        )
        if selected_top_other != "เลือกดูสภาพ...":
            other_count = len(valid_df[(valid_df['สถานะการตรวจ'] == 'ตรวจแล้ว') & (valid_df['สภาพครุภัณฑ์'] == selected_top_other)])
            st.markdown(f"<div style='font-size: 13px; font-weight: bold; color: #1d4ed8; text-align: center; margin-top: -8px;'>จำนวน: {other_count} ราย</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='font-size: 12px; color: #64748b; text-align: center; margin-top: -8px;'>เลือกดูจำนวน</div>", unsafe_allow_html=True)

    st.markdown("<hr style='margin: 12px 0px;'>", unsafe_allow_html=True)

    main_tab1, main_tab2, main_tab3, main_tab4 = st.tabs([
        "🔍 ค้นหา & บันทึกผล", 
        "📱 ตรวจนับด้วยมือถือ (ยิงรหัส/ค้นหาด่วน)",
        "🏷️ สร้าง QR Code", 
        "📥 ส่งออกรายงาน Excel"
    ])
    
    status_options = [
        "โปรดระบุสถานะ",
        "ตรวจแล้ว",
        "ยังไม่ตรวจ"
    ]

    with main_tab1:
        st.subheader("ค้นหาและบันทึกผลการตรวจสอบครุภัณฑ์รายชิ้น")
        
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            search_query = st.text_input("พิมพ์ค้นหา:", placeholder="ชื่อ, หมายเลขครุภัณฑ์...", key="search_main_1")
        with col_s2:
            condition_filter = st.selectbox("กรองสภาพครุภัณฑ์", ["ทั้งหมด"] + condition_options[1:], key="filter_cond_main_1")
        with col_s3:
            status_filter = st.selectbox("กรองสถานะการตรวจ", ["ทั้งหมด", "ตรวจแล้ว", "ยังไม่ตรวจ"], key="filter_main_1")
        with col_s4:
            inspector_filter = st.text_input("กรองผู้ตรวจ:", placeholder="ชื่อผู้ตรวจสอบ...", key="filter_inspector_main")
        
        display_df = df[valid_mask]
        
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

        col_dl_btn, col_space = st.columns([1.2, 3.8])
        with col_dl_btn:
            filtered_buffer = BytesIO()
            display_df.to_excel(filtered_buffer, index=False)
            filtered_data = filtered_buffer.getvalue()
            
            thai_now = datetime.utcnow() + timedelta(hours=7)
            st.download_button(
                label="📥 ดาวน์โหลดรายการที่แสดงนี้ (Excel)",
                data=filtered_data,
                file_name=f"รายงานครุภัณฑ์_เฉพาะที่กรอง_{thai_now.strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        st.markdown("<hr style='margin: 16px 0px;'>", unsafe_allow_html=True)
        st.markdown("### 📝 บันทึก/อัปเดตผลการตรวจสอบ")
        with st.container(border=True):
            col_item, col_badge = st.columns([1.2, 1.8])
            with col_item:
                item_target = st.selectbox(
                    f"เลือกรายการ ({target_column})",
                    options=df[valid_mask][target_column].tolist(),
                    key="main_item_select"
                )
            with col_badge:
                st.markdown("<div style='font-size: 14px; font-weight: 600; margin-bottom: 4px; color: #31333F;'>สถานะปัจจุบันของรายการนี้</div>", unsafe_allow_html=True)
                current_row = df[df[target_column].astype(str) == str(item_target)].iloc[0]
                render_status_badge(
                    current_row['สถานะการตรวจ'],
                    current_row['สภาพครุภัณฑ์'],
                    current_row['ผู้ตรวจ']
                )

            with st.form("audit_form_main", border=False):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    new_condition = st.selectbox("1. สภาพครุภัณฑ์", condition_options, index=0)
                with c2:
                    new_status = st.selectbox("2. สถานะการตรวจ", status_options, index=0)
                with c3:
                    note_text = st.text_input("หมายเหตุ (รายละเอียดเพิ่มเติม)")
                with c4:
                    inspector_name = st.text_input("3. ผู้ตรวจ (ชื่อผู้ตรวจสอบ/กรรมการ)")
                
                btn_col, save_status_col = st.columns([1.2, 1.8])
                with btn_col:
                    submit_button = st.form_submit_button(label="💾 บันทึกผลการตรวจรายการนี้", use_container_width=True)
                with save_status_col:
                    render_save_status_badge(
                        current_row['สถานะการตรวจ'],
                        current_row['วันเดือนปี เวลา ที่ทำการตรวจสอบ']
                    )
                
                if submit_button:
                    if new_status == "โปรดระบุสถานะ":
                        st.error("⚠️ กรุณาเลือก '2. สถานะการตรวจ' ก่อนกดบันทึกครับ")
                    elif new_status == "ตรวจแล้ว" and new_condition == "โปรดระบุสภาพ":
                        st.error("⚠️ กรุณาเลือก '1. สภาพครุภัณฑ์' ก่อนกดบันทึกครับ")
                    else:
                        thai_time = datetime.utcnow() + timedelta(hours=7)
                        current_time = thai_time.strftime("%d/%m/%Y %H:%M:%S")
                        
                        mask = df[target_column].astype(str) == str(item_target)
                        if new_status == "ยังไม่ตรวจ":
                            save_condition = '-'
                            save_status = 'ยังไม่ตรวจ'
                            save_note = '-'
                            save_inspector = '-'
                            save_time = '-'
                        else:
                            save_condition = new_condition
                            save_status = new_status
                            save_note = note_text.strip() if note_text.strip() else '-'
                            save_inspector = inspector_name if inspector_name.strip() else '-'
                            save_time = current_time
                        
                        df.loc[mask, 'สภาพครุภัณฑ์'] = save_condition
                        df.loc[mask, 'สถานะการตรวจ'] = save_status
                        df.loc[mask, 'หมายเหตุ'] = save_note
                        df.loc[mask, 'ผู้ตรวจ'] = save_inspector
                        df.loc[mask, 'วันเดือนปี เวลา ที่ทำการตรวจสอบ'] = save_time
                        
                        save_progress_to_supabase(
                            asset_code=item_target,
                            condition=save_condition,
                            status=save_status,
                            note=save_note,
                            inspector=save_inspector,
                            timestamp=save_time
                        )
                        get_shared_data.clear()
                        st.success(f"✅ บันทึกผลรายการ {item_target} ลง Supabase Cloud เรียบร้อยแล้ว!")
                        st.rerun()

        st.markdown("<hr style='margin: 16px 0px;'>", unsafe_allow_html=True)
        enable_admin_tools = st.checkbox("⚙️ เปิดใช้งานโหมด: แก้ไขรายละเอียดครุภัณฑ์ / เพิ่มรายการใหม่ (สำหรับผู้ดูแลระบบ)", value=False)
        
        if enable_admin_tools:
            st.markdown("### 🛠️ แก้ไขรายละเอียดครุภัณฑ์ / เพิ่มรายการใหม่ (ซิงค์ขึ้น Cloud)")
            
            with st.container(border=True):
                mode_select = st.radio(
                    "เลือกโหมดการทำงาน:",
                    ["✏️ แก้ไขข้อมูลครุภัณฑ์เดิม", "➕ เพิ่มรายการครุภัณฑ์ใหม่ขึ้น Cloud"],
                    horizontal=True
                )
                
                audit_cols_set = {'สภาพครุภัณฑ์', 'สถานะการตรวจ', 'หมายเหตุ', 'ผู้ตรวจ', 'วันเดือนปี เวลา ที่ทำการตรวจสอบ'}
                editable_cols = [c for c in df.columns if c not in audit_cols_set and c != target_column]

                if mode_select == "✏️ แก้ไขข้อมูลครุภัณฑ์เดิม":
                    edit_target = st.selectbox(
                        f"เลือกหมายเลขครุภัณฑ์ที่ต้องการแก้ไขข้อมูล ({target_column})",
                        options=df[valid_mask][target_column].tolist(),
                        key="cloud_edit_item_select"
                    )
                    target_row = df[df[target_column].astype(str) == str(edit_target)].iloc[0]
                    
                    with st.form("cloud_edit_asset_form"):
                        st.caption("พิมพ์แก้ไขข้อมูลในช่องที่ต้องการ (รวมถึงช่อง 'หมายเหตุ') แล้วกดปุ่มบันทึกด้านล่างเพื่ออัปเดตขึ้น Cloud")
                        updated_values = {}
                        cols_ui = st.columns(3)
                        
                        for idx, col_name in enumerate(editable_cols):
                            with cols_ui[idx % 3]:
                                updated_values[col_name] = st.text_input(
                                    col_name,
                                    value=str(target_row[col_name]) if str(target_row[col_name]) not in ['nan', 'None'] else '-'
                                )
                        
                        current_note_val = str(target_row.get('หมายเหตุ', '-'))
                        if current_note_val in ['nan', 'None']:
                            current_note_val = '-'
                        
                        with cols_ui[(len(editable_cols)) % 3]:
                            note_input_val = st.text_input("หมายเหตุ", value=current_note_val, key="edit_extra_note")
                        
                        save_edit_cloud = st.form_submit_button("☁️ บันทึกการแก้ไขข้อมูลนี้ขึ้น Cloud", type="primary", use_container_width=True)
                        if save_edit_cloud:
                            updated_values['หมายเหตุ_ข้อมูลหลัก'] = note_input_val
                            save_progress_to_supabase(
                                asset_code=edit_target,
                                condition=target_row['สภาพครุภัณฑ์'],
                                status=target_row['สถานะการตรวจ'],
                                note=note_input_val,
                                inspector=target_row['ผู้ตรวจ'],
                                timestamp=target_row['วันเดือนปี เวลา ที่ทำการตรวจสอบ'],
                                extra_dict=updated_values
                            )
                            get_shared_data.clear()
                            st.success(f"✅ อัปเดตข้อมูลครุภัณฑ์ {edit_target} ขึ้น Cloud เรียบร้อยแล้ว!")
                            st.rerun()

                else:
                    with st.form("cloud_add_asset_form"):
                        st.caption("กรอกหมายเลขครุภัณฑ์ใหม่ (ต้องมีตัวเลข) และรายละเอียด รวมถึงช่อง 'หมายเหตุ' เพื่อเพิ่มเข้าสู่ระบบ Cloud ถาวร")
                        new_code = st.text_input(f"🌟 {target_column} (จำเป็นต้องกรอกและมีตัวเลข เช่น 605-012600-30099)")
                        
                        new_values = {}
                        cols_ui = st.columns(3)
                        
                        for idx, col_name in enumerate(editable_cols):
                            with cols_ui[idx % 3]:
                                new_values[col_name] = st.text_input(col_name, value="-", key=f"new_col_{idx}")
                        
                        with cols_ui[(len(editable_cols)) % 3]:
                            new_note_val = st.text_input("หมายเหตุ", value="-", key="new_extra_note")

                        save_new_cloud = st.form_submit_button("➕ เพิ่มรายการใหม่และบันทึกขึ้น Cloud", type="primary", use_container_width=True)
                        if save_new_cloud:
                            if not is_valid_asset_code(new_code):
                                st.error(f"⚠️ กรุณากรอก '{target_column}' ให้ถูกต้อง (ต้องมีตัวเลขผสมอยู่ด้วยครับ)")
                            elif str(new_code).strip() in df[target_column].astype(str).str.strip().values:
                                st.warning("⚠️ หมายเลขครุภัณฑ์นี้มีอยู่ในระบบแล้ว กรุณาใช้โหมด 'แก้ไขข้อมูลครุภัณฑ์เดิม' แทนครับ")
                            else:
                                new_values['หมายเหตุ_ข้อมูลหลัก'] = new_note_val
                                save_progress_to_supabase(
                                    asset_code=new_code.strip(),
                                    condition="-",
                                    status="ยังไม่ตรวจ",
                                    note=new_note_val,
                                    inspector="-",
                                    timestamp="-",
                                    extra_dict=new_values
                                )
                                get_shared_data.clear()
                                st.success(f"✅ เพิ่มรายการครุภัณฑ์ใหม่ {new_code} ขึ้น Cloud สำเร็จแล้ว!")
                                st.rerun()

    with main_tab2:
        st.subheader("📱 โหมดตรวจนับหน้างานผ่านมือถือ")
        st.write("ใช้สำหรับเปิดผ่านมือถือหน้างาน เดินตรวจทีละชิ้นโดยสแกน QR Code หรือพิมพ์หมายเลขครุภัณฑ์")
        
        # จัดเรียงใหม่ให้อยู่ในแนวตั้งฝั่งเดียว (ใต้กันลงมาอย่างสวยงาม)
        with st.container(border=True):
            st.markdown("##### 🔎 ค้นหาหรือสแกน QR Code")
            
            if "open_scanner" not in st.session_state:
                st.session_state.open_scanner = False
            
            btn_label = "❌ ปิดกล้องสแกน QR Code" if st.session_state.open_scanner else "📷 กดปุ่มสแกน QR Code หมายเลขพัสดุ"
            if st.button(btn_label, use_container_width=True, type="primary" if not st.session_state.open_scanner else "secondary"):
                st.session_state.open_scanner = not st.session_state.open_scanner
                st.rerun()
            
            if st.session_state.open_scanner:
                render_live_qr_scanner()

            mobile_search = st.text_input(
                "พิมพ์หรือยิงบาร์โค้ดหมายเลขครุภัณฑ์ที่นี่ (แตะค้างแล้วกด 'วาง'):",
                value="",
                key="mob_input_box"
            )

        if mobile_search:
            matched_mob = df[valid_mask][df[valid_mask][target_column].astype(str).str.contains(mobile_search, case=False, na=False)]
            
            if not matched_mob.empty:
                st.success(f"🎯 พบข้อมูลทั้งหมด {len(matched_mob)} รายการ")
                st.dataframe(matched_mob, use_container_width=True)
                
                st.markdown("### 📝 บันทึกผลการตรวจหน้างาน")
                with st.container(border=True):
                    m_col_item, m_col_badge = st.columns([1.2, 1.8])
                    with m_col_item:
                        mob_target = st.selectbox(
                            "เลือกหมายเลขครุภัณฑ์ที่ต้องการบันทึก",
                            options=matched_mob[target_column].tolist(),
                            key="mob_item_select"
                        )
                    with m_col_badge:
                        st.markdown("<div style='font-size: 14px; font-weight: 600; margin-bottom: 4px; color: #31333F;'>สถานะปัจจุบันของรายการนี้</div>", unsafe_allow_html=True)
                        mob_row = df[df[target_column].astype(str) == str(mob_target)].iloc[0]
                        render_status_badge(
                            mob_row['สถานะการตรวจ'],
                            mob_row['สภาพครุภัณฑ์'],
                            mob_row['ผู้ตรวจ']
                        )

                    with st.form("mobile_quick_audit", border=False):
                        mc1, mc2, mc3, mc4 = st.columns(4)
                        with mc1:
                            mob_condition = st.selectbox("1. สภาพครุภัณฑ์", condition_options, index=0, key="m_cond")
                        with mc2:
                            mob_status = st.selectbox("2. สถานะการตรวจ", status_options, index=0, key="m_status")
                        with mc3:
                            mob_note = st.text_input("หมายเหตุ (รายละเอียดเพิ่มเติม)", key="m_note")
                        with mc4:
                            mob_inspector = st.text_input("3. ผู้ตรวจ (ชื่อผู้ตรวจสอบ/กรรมการ)", key="m_insp")
                        
                        m_btn_col, m_save_status_col = st.columns([1.2, 1.8])
                        with m_btn_col:
                            mob_submit = st.form_submit_button(label="💾 บันทึกผลการตรวจทันที", use_container_width=True)
                        with m_save_status_col:
                            render_save_status_badge(
                                mob_row['สถานะการตรวจ'],
                                mob_row['วันเดือนปี เวลา ที่ทำการตรวจสอบ']
                            )
                        
                        if mob_submit:
                            if mob_status == "โปรดระบุสถานะ":
                                st.error("⚠️ กรุณาเลือก '2. สถานะการตรวจ' ก่อนกดบันทึกครับ")
                            elif mob_status == "ตรวจแล้ว" and mob_condition == "โปรดระบุสภาพ":
                                st.error("⚠️ กรุณาเลือก '1. สภาพครุภัณฑ์' ก่อนกดบันทึกครับ")
                            else:
                                thai_time = datetime.utcnow() + timedelta(hours=7)
                                current_time = thai_time.strftime("%d/%m/%Y %H:%M:%S")
                                
                                mask = df[target_column].astype(str) == str(mob_target)
                                if mob_status == "ยังไม่ตรวจ":
                                    m_condition = '-'
                                    m_status_val = 'ยังไม่ตรวจ'
                                    m_note_val = '-'
                                    m_inspector_val = '-'
                                    m_time_val = '-'
                                else:
                                    m_condition = mob_condition
                                    m_status_val = mob_status
                                    m_note_val = mob_note.strip() if mob_note.strip() else '-'
                                    m_inspector_val = mob_inspector if mob_inspector.strip() else '-'
                                    m_time_val = current_time
                                
                                df.loc[mask, 'สภาพครุภัณฑ์'] = m_condition
                                df.loc[mask, 'สถานะการตรวจ'] = m_status_val
                                df.loc[mask, 'หมายเหตุ'] = m_note_val
                                df.loc[mask, 'ผู้ตรวจ'] = m_inspector_val
                                df.loc[mask, 'วันเดือนปี เวลา ที่ทำการตรวจสอบ'] = m_time_val
                                
                                save_progress_to_supabase(
                                    asset_code=mob_target,
                                    condition=m_condition,
                                    status=m_status_val,
                                    note=m_note_val,
                                    inspector=m_inspector_val,
                                    timestamp=m_time_val
                                )
                                get_shared_data.clear()
                                st.session_state.open_scanner = False
                                st.success(f"✅ บันทึกผลครุภัณฑ์หมายเลข {mob_target} ลง Supabase สำเร็จเรียบร้อย!")
                                st.rerun()
            else:
                st.warning("⚠️ ไม่พบหมายเลขครุภัณฑ์นี้ในระบบ ตรวจสอบความถูกต้องอีกครั้งครับ")
        else:
            st.info("👈 พิมพ์ค้นหาหมายเลขครุภัณฑ์ หรือกดปุ่ม **'📷 กดปุ่มสแกน QR Code หมายเลขพัสดุ'** ด้านบนเพื่อเริ่มตรวจสอบได้เลยครับ")

    with main_tab3:
        st.subheader("🏷️ ระบบสร้าง QR Code พร้อมลิงก์สแกนด่วน")
        selected_qr_item = st.selectbox(f"เลือกหมายเลขครุภัณฑ์ที่ต้องการสร้าง QR", options=df[valid_mask][target_column].tolist(), key="gen_qr_tab")
        
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
            except:
                try:
                    font = ImageFont.truetype("DejaVuSans.ttf", 20)
                except:
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

    with main_tab4:
        st.subheader("📥 ดาวน์โหลดรายงานสรุปผลการตรวจสอบประจำปี")
        st.write("ข้อมูลการตรวจสอบทั้งหมด (รวมช่องหมายเหตุและสถานะด้านท้าย) สามารถกดดาวน์โหลดเป็นไฟล์ Excel ได้ทันทีครับ")
        
        output_buffer = BytesIO()
        df[valid_mask].to_excel(output_buffer, index=False)
        output_data = output_buffer.getvalue()
        
        thai_now = datetime.utcnow() + timedelta(hours=7)
        st.download_button(
            label="📊 ดาวน์โหลดรายงาน Excel ผลการตรวจทั้งหมด",
            data=output_data,
            file_name=f"รายงานผลการตรวจครุภัณฑ์_{thai_now.strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
