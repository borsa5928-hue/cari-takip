import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# 1. Google Sheets Bağlantı Fonksiyonu
@st.cache_resource
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    return gspread.authorize(credentials)

client = get_gspread_client()

# 2. Google Tablonuza Erişin ("CariTakip" tablo adınızdır)
sheet = client.open("CariTakip").sheet1 

st.title("📊 Cari Takip Sistemi")

# 3. Verileri Okuma
data = sheet.get_all_records()
df = pd.DataFrame(data)

st.subheader("Mevcut Cari Kayıtları")
if not df.empty:
    st.dataframe(df, use_container_width=True)
else:
    st.info("Henüz tabloda veri bulunmuyor.")

# 4. Yeni Veri Ekleme Formu
st.sidebar.header("Yeni Cari Ekle")
unvan = st.sidebar.text_input("Firma / Kişi Unvanı")
bakiye = st.sidebar.number_input("Bakiye (TL)", value=0.0)

if st.sidebar.button("Kaydet"):
    if unvan:
        sheet.append_row([unvan, bakiye])
        st.sidebar.success("Kayıt başarıyla eklendi!")
        st.rerun()
    else:
        st.sidebar.warning("Lütfen unvan alanını doldurun.")
