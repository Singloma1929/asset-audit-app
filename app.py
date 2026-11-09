if submit_login:
    code_in = login_code.strip().lower()
    pass_in = login_pass.strip()

    # บัญชีสำนักงานหลัก เข้าได้เสมอ ไม่ต้องมีแถวในตาราง
    if code_in == "default_agency" and pass_in == "admin1234":
        st.session_state.is_logged_in = True
        st.session_state.current_agency = "default_agency"
        st.session_state.current_agency_name = "สำนักงานหลัก (Default)"
        st.rerun()
    elif not code_in or not pass_in:
        st.error("⚠️ กรุณากรอกรหัสหน่วยงานและรหัสผ่านให้ครบถ้วน")
    else:
        agencies = get_registered_agencies()
        matched_agency = None
        for ag in agencies:
            if str(ag.get("agency_code", "")).strip().lower() == code_in:
                matched_agency = ag
                break

        if matched_agency:
            stored_pass = str(matched_agency.get("password", "")).strip()
            if stored_pass == pass_in:
                st.session_state.is_logged_in = True
                st.session_state.current_agency = matched_agency["agency_code"]
                st.session_state.current_agency_name = matched_agency["agency_name"]
                st.rerun()
            else:
                st.error("❌ รหัสผ่านไม่ถูกต้อง")
        else:
            st.error("❌ ไม่พบรหัสหน่วยงานนี้ในระบบ")
