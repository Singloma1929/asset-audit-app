import streamlit as st
import pandas as pd
from datetime import datetime
import qrcode
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# ตั้งค่าหน้าเว็บให้เป็นแบบ Wide และใช้ Theme โมเดิร์น
st.set_page_config(
    page_title="ระบบตรวจพัสดุและครุภัณฑ์ราชการ",
    page_icon="🏛️",
    layout="wide"
)

# Custom CSS เพิ่มความสวยงามสไตล์โมเดิร์น
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)

st.title("🏛️ ระบบตรวจพัสดุและครุภัณฑ์ราชการ")
st.write("---")

# ส่วนอัปโหลดไฟล์ที่ Sidebar หรือด้านบน
st.sidebar.header("📁 ตั้งค่าข้อมูลตั้งต้น")
uploaded_file = st.sidebar.file_uploader("อัปโหลดไฟล์ Excel ทะเบียนครุภัณฑ์", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    if uploaded_file.name.endswith('.csv'):
        raw_df = pd.read_csv(uploaded_file, header=None)
    else:
        raw_df = pd.read_excel(uploaded_file, header=None)
    
    header_row = st.sidebar.number_input("ระบุบรรทัดหัวตาราง (Row index)", min_value=0, max_value=len(raw_df)-1, value=4, step=1)
    
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

    # แสดง Progress Bar เปอร์เซ็นต์การตรวจ
    st.write(f"**ความคืบหน้าการตรวจสอบภาพรวม: {progress_pct}%** ({checked_items} จาก {total_items} รายการ)")
    st.progress(progress_pct / 100)

    # แสดงการ์ดตัวเลขสถิติ
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("📦 ทั้งหมด", total_items)
    col2.metric("✅ ปกติ", normal_count)
    col3.metric("⚠️ ชำรุด", damaged_count)
    col4.metric("❌ สูญหาย", lost_count)
    col5.metric("🗑️ จำหน่ายแล้ว", disposed_count)
    col6.metric("🔧 รอซ่อม", repair_count)

    st.write("---")

    # --- 🧭 เมนูด้านข้างสำหรับเลือกใช้งาน ---
    st.sidebar.write("---")
    st.sidebar.subheader("📌 เมนูการใช้งาน")
    app_mode = st.sidebar.radio("เลือกฟังก์ชัน:", ["🔍 ค้นหา & บันทึกผลการตรวจ", "🏷️ ระบบสร้าง QR Code พัสดุ"])

    if app_mode == "🔍 ค้นหา & บันทึกผลการตรวจ":
        st.subheader("🔍 ค้นหาและบันทึกผลการตรวจสอบครุภัณฑ์")
        
        search_query = st.text_input("พิมพ์ค้นหาจากชื่อ, หมายเลขครุภัณฑ์ หรือ ꪜ ข้อมูลอื่นๆ:")
        if search_query:
            filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
        else:
            filtered_df = df

        st.dataframe(filtered_df, use_container_width=True)
        
        with st.form("audit_form_modern"):
            st.subheader("📝 บันทึก/อัปเดตสถานะรายชิ้น")
            item_target = st.selectbox(f"เลือกรายการ ({target_column})", options=df[target_column].tolist())
            new_status = st.selectbox("สถานะการตรวจ", [
                "ปกติ (ตรวจแล้ว)", 
                "ชำรุด", 
                "สูญหาย", 
                "ต้องการซ่อมแซม", 
                "จำหน่ายแล้ว"
            ])
            inspector_name = st.text_input("ชื่อผู้ตรวจสอบ / กรรมการตรวจพัสดุ")
            
            submit_button = st.form_submit_button(label="💾 บันทึกผลการตรวจ")
            
            if submit_button:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                df.loc[df[target_column] == item_target, 'สถานะการตรวจ'] = new_status
                df.loc[df[target_column] == item_target, 'ผู้ตรวจ'] = inspector_name
                df.loc[df[target_column] == item_target, 'วันเวลาที่ตรวจ'] = current_time
                st.success(f"บันทึกผลรายการ {item_target} เรียบร้อยแล้ว! (กรุณาดาวน์โหลดไฟล์ Excel ด้านล่างเพื่อบันทึกข้อมูลเก็บไว้)")

    elif app_mode == "🏷️ ระบบสร้าง QR Code พัสดุ":
        st.subheader("🏷️ ระบบสร้าง QR Code พร้อมข้อความกำกับ (ประหยัดพื้นที่)")
        selected_qr_item = st.selectbox(f"เลือกหมายเลขครุภัณฑ์ที่ต้องการสร้าง QR", options=df[target_column].tolist(), key="gen_qr")
        
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

    # --- 📥 ส่วนส่งออกรายงานภาพรวม ---
    st.write("---")
    st.subheader("📥 ส่งออกรายงานสรุปผลการตรวจประจำปี")
    output_file = "updated_audit_data.xlsx"
    df.to_excel(output_file, index=False)
    with open(output_file, "rb") as f:
        st.download_button(
            label="📊 ดาวน์โหลดรายงาน Excel ผลการตรวจทั้งหมด (พร้อมสถานะและเปอร์เซ็นต์)",
            data=f,
            file_name=f"รายงานผลการตรวจครุภัณฑ์_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("💡 โปรดอัปโหลดไฟล์ Excel ทะเบียนครุภัณฑ์ของคุณที่แถบเมนูด้านซ้าย เพื่อเริ่มต้นใช้งานระบบแดชบอร์ด")
