import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re
import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# ตั้งค่าหน้าเว็บให้เป็นแบบ Wide
st.set_page_config(
    page_title="ระบบตรวจพัสดุและครุภัณฑ์ราชการ",
    page_icon="🏛️",
    layout="wide"
)

st.markdown("""
    <style>
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
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
        height: 40px;
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
        height: 40px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🏛️ ระบบตรวจพัสดุและครุภัณฑ์ราชการ (ระบบกลางประจำหน่วยงาน)")
st.markdown("<hr style='margin: 8px 0px 15px 0px;'>", unsafe_allow_html=True)

PROGRESS_FILE = "audit_progress.csv"
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
        raw_df = pd.read_excel(default_file, header=None)
    
    top_cols = raw_df.iloc[header_row].fillna('').astype(str)
    sub_cols = raw_df.iloc[header_row + 1].fillna('').astype(str)
    
    combined_columns = []
    for t, s in zip(top_cols, sub_cols):
        if s and s != 'None' and s != t:
            combined_columns.append(f"{t} ({s})" if t and t != 'None' else s)
        else:
            combined_columns.append(t if t and t != 'None' else 'Unnamed')

    df = raw_df.iloc[header_row + 2:].copy()
    df.columns = combined_columns
    df = df.dropna(how='all').reset_index(drop=True)

    potential_cols = [c for c in df.columns if any(k in str(c) for k in ['หมายเลขครุภัณฑ์', 'รหัส', 'เลข'])]
    target_col = potential_cols[0] if potential_cols else df.columns[0]

    audit_cols = ['สภาพครุภัณฑ์', 'สถานะการตรวจ', 'ผู้ตรวจ', 'วันเดือนปี เวลา ที่ทำการตรวจสอบ']
    for col in audit_cols:
        if col not in df.columns:
            if col == 'สถานะการตรวจ':
                df[col] = 'ยังไม่ตรวจ'
            else:
                df[col] = '-'

    if os.path.exists(PROGRESS_FILE):
        try:
            saved_df = pd.read_csv(PROGRESS_FILE, dtype=str)
            for _, row in saved_df.iterrows():
                code = str(row[target_col])
                mask = df[target_col].astype(str) == code
                if mask.any():
                    for col in audit_cols:
                        if col in saved_df.columns:
                            df.loc[mask, col] = row[col]
        except Exception:
            pass

    return df, target_col

def save_progress(df, target_col):
    audit_cols = ['สภาพครุภัณฑ์', 'สถานะการตรวจ', 'ผู้ตรวจ', 'วันเดือนปี เวลา ที่ทำการตรวจสอบ']
    try:
        checked_df = df[df['สถานะการตรวจ'] == 'ตรวจแล้ว'][[target_col] + audit_cols]
        checked_df.to_csv(PROGRESS_FILE, index=False, encoding='utf-8-sig')
    except Exception:
        pass

def render_status_badge(status_val, cond_val, inspector_val):
    if status_val == 'ตรวจแล้ว':
        detail = f" (สภาพ: {cond_val} | ผู้ตรวจ: {inspector_val})" if cond_val != '-' else ""
        st.markdown(f"<div class='status-box-green'>✅ ผ่านการตรวจแล้ว{detail}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='status-box-red'>❌ ยังไม่ได้ตรวจ</div>", unsafe_allow_html=True)

df, target_column = get_shared_data()

if df is None:
    st.error("⚠️ ไม่พบไฟล์ข้อมูลกลาง 'default_asset.xlsx' หรือ 'default_asset.xls' บนระบบ โปรดอัปโหลดไฟล์ขึ้นไปไว้ที่หน้าหลักของ GitHub ครับ")
else:
    def is_valid_asset_code(val):
        if pd.isna(val):
            return False
        val_str = str(val).strip()
        if val_str == '' or val_str.lower() == 'nan':
            return False
        return bool(re.search(r'\d', val_str))

    valid_mask = df[target_column].apply(is_valid_asset_code)

    # --- 📊 ส่วนสรุปผลภาพรวม ---
    st.subheader("📊 สรุปสถานะการตรวจสอบประจำปี (ข้อมูลกลางแบบ Real-time)")
    
    valid_df = df[valid_mask]
    total_items = len(valid_df)
    checked_items = len(valid_df[valid_df['สถานะการตรวจ'] == 'ตรวจแล้ว'])
    unchecked_items = len(valid_df[valid_df['สถานะการตรวจ'] == 'ยังไม่ตรวจ'])
    progress_pct = int((checked_items / total_items) * 100) if total_items > 0 else 0
    
    normal_count = len(valid_df[(valid_df['สถานะการตรวจ'] == 'ตรวจแล้ว') & (valid_df['สภาพครุภัณฑ์'] == 'ปกติ')])
    damaged_count = len(valid_df[(valid_df['สถานะการตรวจ'] == 'ตรวจแล้ว') & (valid_df['สภาพครุภัณฑ์'] != 'ปกติ')])

    st.write(f"**ความคืบหน้าการตรวจสอบภาพรวม: {progress_pct}%** (ตรวจแล้ว {checked_items} จาก {total_items} รายการ)")
    st.progress(progress_pct / 100)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("📦 ทั้งหมด", total_items)
    m2.metric("✔️ ตรวจแล้ว", checked_items)
    m3.metric("⏳ ยังไม่ตรวจ", unchecked_items)
    m4.metric("✅ สภาพปกติ", normal_count)
    m5.metric("⚠️ ชำรุด/อื่นๆ", damaged_count)

    st.markdown("<hr style='margin: 15px 0px;'>", unsafe_allow_html=True)

    # --- 🗂️ เมนูหลัก ---
    main_tab1, main_tab2, main_tab3, main_tab4 = st.tabs([
        "🔍 ค้นหา & บันทึกผล", 
        "📱 ตรวจนับด้วยมือถือ (ยิงรหัส/ค้นหาด่วน)",
        "🏷️ สร้าง QR Code", 
        "📥 ส่งออกรายงาน Excel"
    ])

    condition_options = [
        "โปรดระบุสภาพ",
        "ปกติ", 
        "ชำรุด/เสียหาย", 
        "เสื่อมสภาพ/รอจำหน่าย", 
        "สูญหาย"
    ]
    
    status_options = [
        "โปรดระบุสถานะ",
        "ตรวจแล้ว",
        "ยังไม่ตรวจ"
    ]

    with main_tab1:
        st.subheader("ค้นหาและบันทึกผลการตรวจสอบครุภัณฑ์รายชิ้น")
        
        col_search, col_filter = st.columns([3, 1])
        with col_search:
            search_query = st.text_input("พิมพ์ค้นหาจากชื่อ, หมายเลขครุภัณฑ์ หรือข้อมูลอื่นๆ:")
        with col_filter:
            status_filter = st.selectbox("กรองสถานะการตรวจ", ["ทั้งหมด", "ตรวจแล้ว", "ยังไม่ตรวจ"])
        
        display_df = df[valid_mask]
        if status_filter != "ทั้งหมด":
            display_df = display_df[display_df['สถานะการตรวจ'] == status_filter]
        if search_query:
            display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]

        st.dataframe(display_df, use_container_width=True)
        
        st.markdown("### 📝 บันทึก/อัปเดตผลการตรวจสอบ")
        with st.container(border=True):
            # แบ่งครึ่งซ้าย-ขวา: ซ้ายเลือกหมายเลขครุภัณฑ์ ขวาแสดงแถบสถานะสีเขียว/แดงทันที
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
                c1, c2, c3 = st.columns(3)
                with c1:
                    new_condition = st.selectbox("1. สภาพครุภัณฑ์", condition_options, index=0)
                with c2:
                    new_status = st.selectbox("2. สถานะการตรวจ", status_options, index=0)
                with c3:
                    inspector_name = st.text_input("3. ผู้ตรวจ (ชื่อผู้ตรวจสอบ/กรรมการ)")
                
                submit_button = st.form_submit_button(label="💾 บันทึกผลการตรวจรายการนี้")
                
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
                            df.loc[mask, 'สภาพครุภัณฑ์'] = '-'
                            df.loc[mask, 'สถานะการตรวจ'] = 'ยังไม่ตรวจ'
                            df.loc[mask, 'ผู้ตรวจ'] = '-'
                            df.loc[mask, 'วันเดือนปี เวลา ที่ทำการตรวจสอบ'] = '-'
                        else:
                            df.loc[mask, 'สภาพครุภัณฑ์'] = new_condition
                            df.loc[mask, 'สถานะการตรวจ'] = new_status
                            df.loc[mask, 'ผู้ตรวจ'] = inspector_name if inspector_name.strip() else '-'
                            df.loc[mask, 'วันเดือนปี เวลา ที่ทำการตรวจสอบ'] = current_time
                        
                        save_progress(df, target_column)
                        st.success(f"✅ บันทึกผลรายการ {item_target} เรียบร้อยแล้ว!")
                        st.rerun()

    with main_tab2:
        st.subheader("📱 โหมดตรวจนับหน้างานผ่านมือถือ")
        st.write("ใช้สำหรับเปิดผ่านมือถือหน้างาน เดินตรวจทีละชิ้นโดยสแกน QR Code หรือพิมพ์หมายเลขครุภัณฑ์")
        
        query_params = st.query_params
        default_mob_search = query_params.get("scan", "")
        
        mobile_search = st.text_input("🔎 พิมพ์หรือยิงบาร์โค้ดหมายเลขครุภัณฑ์ที่นี่:", value=default_mob_search, key="mob_input")
        
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
                        mc1, mc2, mc3 = st.columns(3)
                        with mc1:
                            mob_condition = st.selectbox("1. สภาพครุภัณฑ์", condition_options, index=0, key="m_cond")
                        with mc2:
                            mob_status = st.selectbox("2. สถานะการตรวจ", status_options, index=0, key="m_status")
                        with mc3:
                            mob_inspector = st.text_input("3. ผู้ตรวจ (ชื่อผู้ตรวจสอบ/กรรมการ)", key="m_insp")
                        
                        mob_submit = st.form_submit_button(label="💾 บันทึกผลการตรวจทันที")
                        
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
                                    df.loc[mask, 'สภาพครุภัณฑ์'] = '-'
                                    df.loc[mask, 'สถานะการตรวจ'] = 'ยังไม่ตรวจ'
                                    df.loc[mask, 'ผู้ตรวจ'] = '-'
                                    df.loc[mask, 'วันเดือนปี เวลา ที่ทำการตรวจสอบ'] = '-'
                                else:
                                    df.loc[mask, 'สภาพครุภัณฑ์'] = mob_condition
                                    df.loc[mask, 'สถานะการตรวจ'] = mob_status
                                    df.loc[mask, 'ผู้ตรวจ'] = mob_inspector if mob_inspector.strip() else '-'
                                    df.loc[mask, 'วันเดือนปี เวลา ที่ทำการตรวจสอบ'] = current_time
                                
                                save_progress(df, target_column)
                                st.success(f"✅ บันทึกผลครุภัณฑ์หมายเลข {mob_target} สำเร็จเรียบร้อย!")
                                st.rerun()
            else:
                st.warning("⚠️ ไม่พบหมายเลขครุภัณฑ์นี้ในระบบ ตรวจสอบความถูกต้องอีกครั้งครับ")

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
        st.write("ข้อมูลการตรวจสอบทั้งหมด (รวม 4 ช่องสถานะด้านท้าย) สามารถกดดาวน์โหลดเป็นไฟล์ Excel ได้ทันทีครับ")
        
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
