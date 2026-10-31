import streamlit as st
import pandas as pd
from datetime import datetime
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
    </style>
""", unsafe_allow_html=True)

st.title("🏛️ ระบบตรวจพัสดุและครุภัณฑ์ราชการ (ระบบกลางประจำหน่วยงาน)")
st.markdown("<hr style='margin: 8px 0px 15px 0px;'>", unsafe_allow_html=True)

# ตรวจสอบไฟล์กลาง (.xlsx หรือ .xls)
if os.path.exists("default_asset.xlsx"):
    DEFAULT_FILE = "default_asset.xlsx"
elif os.path.exists("default_asset.xls"):
    DEFAULT_FILE = "default_asset.xls"
else:
    DEFAULT_FILE = None

header_row = 4  # แถวหัวตารางมาตรฐานจากไฟล์ของคุณ

if DEFAULT_FILE is None:
    st.error("⚠️ ไม่พบไฟล์ข้อมูลกลาง 'default_asset.xlsx' หรือ 'default_asset.xls' บนระบบ โปรดอัปโหลดไฟล์ขึ้นไปไว้ที่หน้าหลักของ GitHub ครับ")
else:
    # โหลดไฟล์แบบอ่านโครงสร้างทั้งหมดเพื่อเก็บหัวตารางเดิมไว้
    if DEFAULT_FILE.endswith('.csv'):
        raw_df = pd.read_csv(DEFAULT_FILE, header=None)
    else:
        raw_df = pd.read_excel(DEFAULT_FILE, header=None)
    
    top_cols = raw_df.iloc[header_row].fillna('').astype(str)
    sub_cols = raw_df.iloc[header_row + 1].fillna('').astype(str)
    
    combined_columns = []
    for t, s in zip(top_cols, sub_cols):
        if s and s != 'None' and s != t:
            combined_columns.append(f"{t} ({s})" if t and t != 'None' else s)
        else:
            combined_columns.append(t if t and t != 'None' else 'Unnamed')

    # ดึงข้อมูลส่วนตาราง
    data_part = raw_df.iloc[header_row + 2:].copy()
    data_part.columns = combined_columns
    data_part = data_part.dropna(how='all').reset_index(drop=True)

    potential_cols = [c for c in data_part.columns if any(k in str(c) for k in ['หมายเลขครุภัณฑ์', 'รหัส', 'เลข'])]
    target_column = potential_cols[0] if potential_cols else data_part.columns[0]

    def is_valid_asset_code(val):
        if pd.isna(val):
            return False
        val_str = str(val).strip()
        if val_str == '' or val_str.lower() == 'nan':
            return False
        return bool(re.search(r'\d', val_str))

    # กรองเฉพาะแถวที่มีหมายเลขครุภัณฑ์จริง
    valid_mask = data_part[target_column].apply(is_valid_asset_code)
    
    # ตรวจสอบและสร้างคอลัมน์สถานะถ้ายังไม่มีในไฟล์ Excel ต้นฉบับ
    audit_columns = ['สถานะการตรวจ', 'ผู้ตรวจ', 'วันเวลาที่ตรวจ']
    for col in audit_columns:
        if col not in data_part.columns:
            data_part[col] = '-' if col != 'สถานะการตรวจ' else 'ยังไม่ได้ตรวจ'

    # --- 📊 ส่วนสรุปผลภาพรวม ---
    st.subheader("📊 สรุปสถานะการตรวจสอบประจำปี (ข้อมูลกลาง)")
    
    total_items = len(data_part[valid_mask])
    checked_items = len(data_part[valid_mask][data_part['สถานะการตรวจ'] != 'ยังไม่ได้ตรวจ'])
    progress_pct = int((checked_items / total_items) * 100) if total_items > 0 else 0
    
    normal_count = len(data_part[valid_mask][data_part['สถานะการตรวจ'] == 'ปกติ (ตรวจแล้ว)'])
    damaged_count = len(data_part[valid_mask][data_part['สถานะการตรวจ'] == 'ชำรุด'])
    lost_count = len(data_part[valid_mask][data_part['สถานะการตรวจ'] == 'สูญหาย'])
    disposed_count = len(data_part[valid_mask][data_part['สถานะการตรวจ'] == 'จำหน่ายแล้ว'])
    repair_count = len(data_part[valid_mask][data_part['สถานะการตรวจ'] == 'ต้องการซ่อมแซม'])

    st.write(f"**ความคืบหน้าการตรวจสอบภาพรวม: {progress_pct}%** ({checked_items} จาก {total_items} รายการ)")
    st.progress(progress_pct / 100)

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("📦 ทั้งหมด", total_items)
    m2.metric("✅ ปกติ", normal_count)
    m3.metric("⚠️ ชำรุด", damaged_count)
    m4.metric("❌ สูญหาย", lost_count)
    m5.metric("🗑️ จำหน่ายแล้ว", disposed_count)
    m6.metric("🔧 รอซ่อม", repair_count)

    st.markdown("<hr style='margin: 15px 0px;'>", unsafe_allow_html=True)

    # --- 🗂️ เมนูหลัก ---
    main_tab1, main_tab2, main_tab3, main_tab4 = st.tabs([
        "🔍 ค้นหา & บันทึกผล", 
        "📱 ตรวจนับด้วยมือถือ (ยิงรหัส/ค้นหาด่วน)",
        "🏷️ สร้าง QR Code", 
        "📥 ส่งออกรายงาน Excel"
    ])

    with main_tab1:
        st.subheader("ค้นหาและบันทึกผลการตรวจสอบครุภัณฑ์รายชิ้น")
        search_query = st.text_input("พิมพ์ค้นหาจากชื่อ, หมายเลขครุภัณฑ์ หรือข้อมูลอื่นๆ:")
        
        display_df = data_part[valid_mask]
        if search_query:
            display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]

        st.dataframe(display_df, use_container_width=True)
        
        with st.form("audit_form_main"):
            st.subheader("📝 บันทึก/อัปเดตสถานะ")
            item_target = st.selectbox(f"เลือกรายการ ({target_column})", options=data_part[valid_mask][target_column].tolist())
            new_status = st.selectbox("สถานะการตรวจ", [
                "ปกติ (ตรวจแล้ว)", 
                "ชำรุด", 
                "สูญหาย", 
                "ต้องการซ่อมแซม", 
                "จำหน่ายแล้ว"
            ])
            inspector_name = st.text_input("ชื่อผู้ตรวจสอบ / กรรมการตรวจพัสดุ")
            
            submit_button = st.form_submit_button(label="💾 บันทึกผลการตรวจรายการนี้")
            
            if submit_button:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # อัปเดตข้อมูลลงใน DataFrame หลัก
                data_part.loc[data_part[target_column] == item_target, 'สถานะการตรวจ'] = new_status
                data_part.loc[data_part[target_column] == item_target, 'ผู้ตรวจ'] = inspector_name
                data_part.loc[data_part[target_column] == item_target, 'วันเวลาที่ตรวจ'] = current_time
                
                # เขียนทับข้อมูลกลับลงไฟล์กลางทันที เพื่อให้ข้อมูลบันทึกถาวร
                raw_df.iloc[header_row + 2:header_row + 2 + len(data_part)] = data_part.values
                if DEFAULT_FILE.endswith('.xlsx'):
                    raw_df.to_excel(DEFAULT_FILE, index=False, header=False)
                else:
                    # กรณีไฟล์เดิมเป็น .xls เซฟแปลงเป็น .xlsx เพื่อให้รองรับการเขียนทับอย่างไร้ปัญหา
                    DEFAULT_FILE = "default_asset.xlsx"
                    raw_df.to_excel(DEFAULT_FILE, index=False, header=False)
                
                st.success(f"✅ บันทึกผลรายการ {item_target} เรียบร้อยและบันทึกลงระบบกลางสำเร็จ!")
                st.rerun()

    with main_tab2:
        st.subheader("📱 โหมดตรวจนับหน้างานผ่านมือถือ")
        st.write("ใช้สำหรับเปิดผ่านมือถือหน้างาน เดินตรวจทีละชิ้นโดยพิมพ์หรือยิงบาร์โค้ด/หมายเลขครุภัณฑ์เพื่อเช็กสถานะทันที")
        
        query_params = st.query_params
        default_mob_search = query_params.get("scan", "")
        
        mobile_search = st.text_input("🔎 พิมพ์หรือยิงบาร์โค้ดหมายเลขครุภัณฑ์ที่นี่:", value=default_mob_search, key="mob_input")
        
        if mobile_search:
            matched_mob = data_part[valid_mask][data_part[valid_mask][target_column].astype(str).str.contains(mobile_search, case=False, na=False)]
            
            if not matched_mob.empty:
                st.success(f"🎯 พบข้อมูลทั้งหมด {len(matched_mob)} รายการ")
                st.dataframe(matched_mob, use_container_width=True)
                
                with st.form("mobile_quick_audit"):
                    st.subheader("📝 บันทึกผลการตรวจหน้างาน")
                    mob_target = st.selectbox("เลือกหมายเลขครุภัณฑ์ที่ต้องการบันทึก", options=matched_mob[target_column].tolist())
                    mob_status = st.selectbox("สถานะการตรวจ", [
                        "ปกติ (ตรวจแล้ว)", 
                        "ชำรุด", 
                        "สูญหาย", 
                        "ต้องการซ่อมแซม", 
                        "จำหน่ายแล้ว"
                    ], key="m_status")
                    mob_inspector = st.text_input("ชื่อผู้ตรวจสอบ / กรรมการ", key="m_insp")
                    
                    mob_submit = st.form_submit_button(label="💾 บันทึกผลการตรวจทันที")
                    
                    if mob_submit:
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        data_part.loc[data_part[target_column] == mob_target, 'สถานะการตรวจ'] = mob_status
                        data_part.loc[data_part[target_column] == mob_target, 'ผู้ตรวจ'] = mob_inspector
                        data_part.loc[data_part[target_column] == mob_target, 'วันเวลาที่ตรวจ'] = current_time
                        
                        raw_df.iloc[header_row + 2:header_row + 2 + len(data_part)] = data_part.values
                        if DEFAULT_FILE.endswith('.xlsx'):
                            raw_df.to_excel(DEFAULT_FILE, index=False, header=False)
                        else:
                            DEFAULT_FILE = "default_asset.xlsx"
                            raw_df.to_excel(DEFAULT_FILE, index=False, header=False)
                            
                        st.success(f"✅ บันทึกผลครุภัณฑ์หมายเลข {mob_target} สำเร็จเรียบร้อย!")
                        st.rerun()
            else:
                st.warning("⚠️ ไม่พบหมายเลขครุภัณฑ์นี้ในระบบ ตรวจสอบความถูกต้องอีกครั้งครับ")

    with main_tab3:
        st.subheader("🏷️ ระบบสร้าง QR Code พร้อมลิงก์สแกนด่วน")
        selected_qr_item = st.selectbox(f"เลือกหมายเลขครุภัณฑ์ที่ต้องการสร้าง QR", options=data_part[valid_mask][target_column].tolist(), key="gen_qr_tab")
        
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
        st.write("ข้อมูลการตรวจสอบทั้งหมดถูกอัปเดตแบบเรียลไทม์ สามารถดาวน์โหลดรายงานไปใช้ได้ทันทีครับ")
        
        output_buffer = BytesIO()
        data_part.to_excel(output_buffer, index=False)
        output_data = output_buffer.getvalue()
        
        st.download_button(
            label="📊 ดาวน์โหลดรายงาน Excel ผลการตรวจทั้งหมด",
            data=output_data,
            file_name=f"รายงานผลการตรวจครุภัณฑ์_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
