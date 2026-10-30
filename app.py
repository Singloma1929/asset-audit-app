import streamlit as st
import pandas as pd
from datetime import datetime
import qrcode
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

st.set_page_config(page_title="ระบบตรวจพัสดุครุภัณฑ์ราชการ", layout="wide")

st.title("🏛️ ระบบตรวจพัสดุและครุภัณฑ์ราชการ")
st.write("---")

st.subheader("📁 1. จัดการข้อมูลตั้งต้น")
uploaded_file = st.file_uploader("อัปโหลดไฟล์ Excel ทะเบียนครุภัณฑ์เดิมของคุณ", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    if uploaded_file.name.endswith('.csv'):
        raw_df = pd.read_csv(uploaded_file, header=None)
    else:
        raw_df = pd.read_excel(uploaded_file, header=None)
    
    header_row = st.number_input("ระบุบรรทัด (Row index) ที่เป็นหัวตารางหลัก", min_value=0, max_value=len(raw_df)-1, value=4, step=1)
    
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
    
    # เพิ่มคอลัมน์ตรวจสอบ
    audit_columns = ['สถานะการตรวจ', 'ผู้ตรวจ', 'วันเวลาที่ตรวจ']
    for col in audit_columns:
        if col not in df.columns:
            if col == 'สถานะการตรวจ':
                df[col] = 'ยังไม่ได้ตรวจ'
            else:
                df[col] = '-'

    st.success("โหลดข้อมูลและจัดโครงสร้างสำเร็จ!")

    # ค้นหาคอลัมน์หมายเลขครุภัณฑ์
    potential_cols = [c for c in df.columns if any(k in str(c) for k in ['หมายเลขครุภัณฑ์', 'รหัส', 'เลข'])]
    target_column = potential_cols[0] if potential_cols else df.columns[0]

    # แบ่งแท็บการใช้งาน
    tab1, tab2 = st.tabs(["🔍 ค้นหา & บันทึกผลการตรวจ", "🏷️ ระบบสร้าง QR Code พัสดุ"])

    with tab1:
        st.subheader("จัดการและบันทึกผลการตรวจสอบครุภัณฑ์")
        search_query = st.text_input("พิมพ์ค้นหาจากชื่อ หรือ หมายเลขครุภัณฑ์:")
        
        if search_query:
            filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
        else:
            filtered_df = df

        st.dataframe(filtered_df, use_container_width=True)
        
        with st.form("audit_form_tab1"):
            item_target = st.selectbox(f"เลือกรายการจาก ({target_column})", options=df[target_column].tolist())
            new_status = st.selectbox("สถานะการตรวจ", ["ปกติ (ตรวจแล้ว)", "ชำรุด", "สูญหาย", "ต้องการซ่อมแซม"])
            inspector_name = st.text_input("ชื่อผู้ตรวจ")
            
            submit_button = st.form_submit_button(label="บันทึกผลการตรวจ")
            
            if submit_button:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                df.loc[df[target_column] == item_target, 'สถานะการตรวจ'] = new_status
                df.loc[df[target_column] == item_target, 'ผู้ตรวจ'] = inspector_name
                df.loc[df[target_column] == item_target, 'วันเวลาที่ตรวจ'] = current_time
                st.success(f"บันทึกผลรายการ {item_target} สำเร็จ!")

    with tab2:
        st.subheader("🏷️ สร้าง QR Code พร้อมข้อความกำกับชิดขอบ (ประหยัดพื้นที่)")
        selected_qr_item = st.selectbox(f"เลือกหมายเลขครุภัณฑ์ที่ต้องการสร้าง QR", options=df[target_column].tolist(), key="gen_qr")
        
        if selected_qr_item:
            # 1. สร้าง QR Code
            qr = qrcode.QRCode(version=1, box_size=10, border=2) # ลด border รอบนอกให้แคบลงนิดหน่อยเพื่อให้กระชับ
            qr.add_data(str(selected_qr_item))
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
            
            qr_width, qr_height = qr_img.size
            padding_bottom = 30  # ลดพื้นที่ส่วนเกินด้านล่างให้ชิดขึ้น
            new_img = Image.new('RGB', (qr_width, qr_height + padding_bottom), 'white')
            new_img.paste(qr_img, (0, 0))
            
            # 2. วาดข้อความหมายเลขครุภัณฑ์ให้ชิดติดขอบล่างของ QR Code
            draw = ImageDraw.Draw(new_img)
            text_to_print = f"No: {selected_qr_item}"
            
            try:
                font = ImageFont.truetype("arial.ttf", 18)
            except:
                font = ImageFont.load_default()
                
            bbox = draw.textbbox((0, 0), text_to_print, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = (qr_width - text_width) / 2
            # วางตำแหน่งให้ชิดติดขอบล่างพอดี (ห่างจากขอบล่างสุดประมาณ 4 พิกเซล)
            text_y = qr_height - 2 
            
            draw.text((text_x, text_y), text_to_print, fill="black", font=font)
            
            # 3. แปลงภาพเพื่อแสดงผลและดาวน์โหลด
            buf = BytesIO()
            new_img.save(buf, format="PNG")
            byte_im = buf.getvalue()
            
            st.image(byte_im, caption=f"ป้าย QR Code กระชับประหยัดพื้นที่: {selected_qr_item}", width=220)
            st.download_button(
                label=f"📥 ดาวน์โหลดรูปป้าย QR Code ({selected_qr_item})",
                data=byte_im,
                file_name=f"QRCode_Label_{selected_qr_item}.png",
                mime="image/png"
            )

    # ส่วนส่งออกข้อมูล Excel ภาพรวม
    st.write("---")
    st.subheader("📥 ส่งออกข้อมูลทั้งหมด")
    output_file = "updated_audit_data.xlsx"
    df.to_excel(output_file, index=False)
    with open(output_file, "rb") as f:
        st.download_button(
            label="📥 ดาวน์โหลดไฟล์ Excel ผลการตรวจทั้งหมด (พร้อมสถานะใหม่)",
            data=f,
            file_name="ทะเบียนครุภัณฑ์_ผลการตรวจ_อัปเดตแล้ว.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("💡 โปรดอัปโหลดไฟล์ Excel ทะเบียนครุภัณฑ์ของคุณที่เมนูด้านบน เพื่อเริ่มต้นใช้งานระบบ")