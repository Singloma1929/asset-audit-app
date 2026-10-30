import streamlit as st
import pandas as pd
from datetime import datetime
import qrcode
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# ตั้งค่าหน้าเว็บให้เป็นแบบ Wide
st.set_page_config(
    page_title="ระบบตรวจพัสดุและครุภัณฑ์ราชการ",
    page_icon="🏛️",
    layout="wide"
)

# ปรับแต่ง CSS ให้หน้าจอมีความกระชับสวยงาม
st.markdown("""
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    h1 {
        font-size: 1.8rem !important;
        margin-bottom: 0px !important;
    }
    </style>
""", unsafe_allow_html=True)

# 4. ย่อหัวข้อให้กระชับขึ้น
st.setHeader = st.title("🏛️ ระบบตรวจพัสดุและครุภัณฑ์ราชการ")
st.markdown("<hr style='margin: 10px 0px 15px 0px;'>", unsafe_allow_html=True)

# 1 & 2 & 3. จัดกลุ่มอัปโหลด, สถานะ และปรับช่อง Row index ให้สั้นลง อยู่ในระนาบเดียวกัน
col_file, col_status, col_row = st.columns([2.5, 1.2, 1.2])

with col_file:
    uploaded_file = st.file_uploader("📁 อัปโหลดไฟล์ Excel ทะเบียนครุภัณฑ์", type=["xlsx", "xls", "csv"])

with col_status:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True) # จัดตำแหน่งความสูงให้ตรงกัน
    if uploaded_file is not None:
        st.success("✅ โหลดข้อมูลสำเร็จ!")
    else:
        st.info("💡 รออัปโหลดไฟล์")

with col_row:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    header_row = st.number_input("แถวหัวตาราง (Row index)", min_value=0, value=4, step=1)

if uploaded_file is not None:
    if uploaded_file.name.endswith('.csv'):
        raw_df = pd.read_csv(uploaded_file, header=None)
    else:
        raw_df = pd.read_excel(uploaded_file, header=None)
    
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
    
    # เพิ่มคอลัมน์ตรวจสอบถ้ายังไม่มี
    audit_columns = ['สถานะการตรวจ', 'ผู้ตรวจ', 'วันเวลาที่ตรวจ']
    for col in audit_columns:
        if col not in df.columns:
            if col == 'สถานะการตรวจ':
                df[col] = 'ยังไม่ได้ตรวจ'
            else:
                df[col] = '-'

    # ค้นหาคอลัมน์หมายเลขครุภัณฑ์
    potential_cols = [c for c in df.columns if any(k in str(c) for k in ['หมายเลขครุภัณฑ์', 'รหัส', 'เลข'])]
    target_column = potential_cols[0] if potential_cols else df.columns[0]

    st.markdown("<hr style='margin: 15px 0px;'>", unsafe_allow_html=True)

    # --- 📊 ส่วนสรุปผลภาพรวม (Dashboard Metrics) ---
    st.subheader("📊 สรุปสถานะการตรวจสอบประจำปี")
    
    total_items = len(df)
    checked_items = len(df[df['สถานะการตรวจ'] != 'ยังไม่ได้ตรวจ'])
    progress_pct = int((checked_items / total_items) * 100) if total_items > 0 else 0
    
    normal_count = len(df[df['สถานะการตรวจ'] == 'ปกติ (ตรวจแล้ว)'])
    damaged_count = len(df[df['สถานะการตรวจ'] == 'ชำรุด'])
    lost_count = len(df[df['สถานะการตรวจ'] == 'สูญหาย'])
    disposed_count = len(df[df['สถานะการตรวจ'] == 'จำหน่ายแล้ว'])
    repair_count = len(df[df['สถานะการตรวจ'] == 'ต้องการซ่อมแซม'])

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

    # --- 🗂️ เมนูหลัก (ย้ายปุ่มสร้าง QR และ ส่งออก มาไว้ด้านบนคู่กันตามขอ) ---
    main_tab1, main_tab2, main_tab3 = st.tabs([
        "🔍 ค้นหา & บันทึกผลการตรวจ", 
        "🏷️ สร้าง QR Code พัสดุ", 
        "📥 ส่งออกรายงาน Excel"
    ])

    with main_tab1:
        st.subheader("ค้นหาและบันทึกผลการตรวจสอบครุภัณฑ์รายชิ้น")
        search_query = st.text_input("พิมพ์ค้นหาจากชื่อ, หมายเลขครุภัณฑ์ หรือข้อมูลอื่นๆ:")
        
        if search_query:
            filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
        else:
            filtered_df = df

        st.dataframe(filtered_df, use_container_width=True)
        
        with st.form("audit_form_main"):
            st.subheader("📝 บันทึก/อัปเดตสถานะ")
            item_target = st.selectbox(f"เลือกรายการ ({target_column})", options=df[target_column].tolist())
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
                df.loc[df[target_column] == item_target, 'สถานะการตรวจ'] = new_status
                df.loc[df[target_column] == item_target, 'ผู้ตรวจ'] = inspector_name
                df.loc[df[target_column] == item_target, 'วันเวลาที่ตรวจ'] = current_time
                st.success(f"บันทึกผลรายการ {item_target} เรียบร้อยแล้ว! (อย่าลืมไปที่แท็บ 'ส่งออกรายงาน Excel' เพื่อดาวน์โหลดไฟล์เก็บไว้)")

    with main_tab2:
        st.subheader("🏷️ ระบบสร้าง QR Code พร้อมข้อความกำกับ")
        selected_qr_item = st.selectbox(f"เลือกหมายเลขครุภัณฑ์ที่ต้องการสร้าง QR", options=df[target_column].tolist(), key="gen_qr_tab")
        
        if selected_qr_item:
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(str(selected_qr_item))
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
            
            qr_width, qr_height = qr_img.size
            padding_bottom = 30
            new_img = Image.new('RGB', (qr_width, qr_height + padding_bottom), 'white')
            new_img.paste(qr_img, (0, 0))
            
            draw = ImageDraw.Draw(new_img)
            text_to_print = f"No: {selected_qr_item}"
            
            try:
                font = ImageFont.truetype("arial.ttf", 18)
            except:
                font = ImageFont.load_default()
                
            bbox = draw.textbbox((0, 0), text_to_print, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = (qr_width - text_width) / 2
            text_y = qr_height - 2 
            
            draw.text((text_x, text_y), text_to_print, fill="black", font=font)
            
            buf = BytesIO()
            new_img.save(buf, format="PNG")
            byte_im = buf.getvalue()
            
            st.image(byte_im, caption=f"ป้าย QR Code: {selected_qr_item}", width=220)
            st.download_button(
                label=f"📥 ดาวน์โหลดรูปป้าย QR Code ({selected_qr_item})",
                data=byte_im,
                file_name=f"QRCode_Label_{selected_qr_item}.png",
                mime="image/png"
            )

    with main_tab3:
        st.subheader("📥 ดาวน์โหลดรายงานสรุปผลการตรวจสอบประจำปี")
        st.write("ข้อมูลทั้งหมดที่มีการอัปเดตสถานะ จะถูกรวมอยู่ในไฟล์นี้เพื่อนำไปรายงานผู้บริหารหรือแนบเอกสารราชการครับ")
        
        output_file = "updated_audit_data.xlsx"
        df.to_excel(output_file, index=False)
        with open(output_file, "rb") as f:
            st.download_button(
                label="📊 ดาวน์โหลดรายงาน Excel ผลการตรวจทั้งหมด (พร้อมเปอร์เซ็นต์และสถานะใหม่)",
                data=f,
                file_name=f"รายงานผลการตรวจครุภัณฑ์_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
