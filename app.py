import io
import os
import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# --- VERİTABANI BAĞLANTISI ---
DB_NAME = "cari_takip.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  # Müşteriler Tablosu
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS musteriler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            telefon TEXT,
            adres TEXT
        )
    """)
  # Cari Hareketler Tablosu (Borç / Alacak)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS hareketler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            musteri_id INTEGER,
            tarih TEXT,
            islem_turu TEXT,
            tutar REAL,
            aciklama TEXT,
            FOREIGN KEY (musteri_id) REFERENCES musteriler (id)
        )
    """)
  conn.commit()
  conn.close()


init_db()

# --- ARAYÜZ (MOBİL UYUMLU) ---
st.set_page_config(
    page_title="Toptancı Cari Takip", page_icon="📦", layout="centered"
)

st.title("📦 Toptancı Cari & Borç Takip")
st.markdown("---")

# Menü Seçimi
menu = st.sidebar.selectbox(
    "Menü",
    [
        "Müşteri Listesi & Ekstre",
        "Yeni Müşteri Ekle",
        "İşlem Ekle (Borç/Ödeme)",
        "Tüm Raporlar (Excel)",
    ],
)

# --- 1. MÜŞTERİ LİSTESİ & EKSTRE ---
if menu == "Müşteri Listesi & Ekstre":
  st.header("👥 Müşteriler ve Cari Hesaplar")

  conn = sqlite3.connect(DB_NAME)
  musteriler_df = pd.read_sql_query("SELECT * FROM musteriler", conn)

  if musteriler_df.empty:
    st.info(
        "Henüz kayıtlı müşteri yok. Sol menüden 'Yeni Müşteri Ekle' diyerek"
        " başlayın."
    )
  else:
    secilen_musteri = st.selectbox(
        "Müşteri Seçin",
        musteriler_df["ad"].tolist(),
    )
    musteri_id = musteriler_df[musteriler_df["ad"] == secilen_musteri][
        "id"
    ].values[0]

    m_info = musteriler_df[musteriler_df["id"] == musteri_id].iloc[0]
    st.write(
        f"📞 **Telefon:** {m_info['telefon']} | 📍 **Adres:** {m_info['adres']}"
    )

    hareketler_df = pd.read_sql_query(
        f"SELECT tarih, islem_turu, tutar, aciklama FROM hareketler WHERE"
        f" musteri_id = {musteri_id}",
        conn,
    )

    if not hareketler_df.empty:
      toplam_borc = hareketler_df[
          hareketler_df["islem_turu"] == "Borç (Satış / Mal Verildi)"
      ]["tutar"].sum()
      toplam_odeme = hareketler_df[
          hareketler_df["islem_turu"] == "Ödeme (Tahsilat / Para Alındı)"
      ]["tutar"].sum()
      bakiye = toplam_borc - toplam_odeme

      col1, col2, col3 = st.columns(3)
      col1.metric("Toplam Borç (Mal)", f"{toplam_borc:,.2f} ₺")
      col2.metric("Yapılan Ödeme", f"{toplam_odeme:,.2f} ₺")
      col3.metric("Güncel Bakiye", f"{bakiye:,.2f} ₺")

      st.markdown("### 📋 Hesap Ekstresi")
      st.dataframe(hareketler_df, use_container_width=True)

      def create_pdf(m_ad, m_tel, df, bky):
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        c.drawString(50, height - 50, f"Cari Hesap Ekstresi - {m_ad}")
        c.drawString(
            50,
            height - 70,
            f"Telefon: {m_tel} | Tarih:"
            f" {datetime.now().strftime('%d.%m.%Y')}",
        )
        c.line(50, height - 80, width - 50, height - 80)

        y = height - 110
        c.drawString(50, y, "Tarih")
        c.drawString(150, y, "İşlem Türü")
        c.drawString(300, y, "Tutar")
        c.drawString(400, y, "Açıklama")
        y -= 20
        c.line(50, y, width - 50, y)
        y -= 20

        for index, row in df.iterrows():
          if y < 50:
            c.showPage()
            y = height - 50
          c.drawString(50, y, str(row["tarih"]))
          c.drawString(150, y, str(row["islem_turu"]))
          c.drawString(300, y, f"{row['tutar']:,.2f} ₺")
          c.drawString(400, y, str(row["aciklama"]))
          y -= 20

        y -= 10
        c.line(50, y, width - 50, y)
        y -= 25
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"GÜNCEL KALAN BAKİYE: {bky:,.2f} TL")

        c.save()
        buffer.seek(0)
        return buffer

      pdf_data = create_pdf(
          secilen_musteri, m_info["telefon"], hareketler_df, bakiye
      )
      st.download_button(
          label="📄 PDF Ekstre İndir / Gönder",
          data=pdf_data,
          file_name=f"{secilen_musteri}_ekstre.pdf",
          mime="application/pdf",
      )
    else:
      st.info("Bu müşteriye ait henüz bir işlem girilmemiş.")
  conn.close()

# --- 2. YENİ MÜŞTERİ EKLE ---
elif menu == "Yeni Müşteri Ekle":
  st.header("➕ Yeni Müşteri Kaydı")
  with st.form("musteri_form"):
    ad = st.text_input("Müşteri / Firma Adı")
    telefon = st.text_input("Telefon Numarası")
    adres = st.text_area("Adres Bilgisi")
    submit = st.form_submit_button("Müşteriyi Kaydet")

    if submit:
      if ad:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO musteriler (ad, telefon, adres) VALUES (?, ?, ?)",
            (ad, telefon, adres),
        )
        conn.commit()
        conn.close()
        st.success(f"'{ad}' başarıyla eklendi!")
      else:
        st.error("Lütfen müşteri adını boş bırakmayın.")

# --- 3. İŞLEM EKLE (BORÇ / ÖDEME) ---
elif menu == "İşlem Ekle (Borç/Ödeme)":
  st.header("💰 Borç veya Tahsilat Ekle")

  conn = sqlite3.connect(DB_NAME)
  musteriler_df = pd.read_sql_query("SELECT * FROM musteriler", conn)

  if musteriler_df.empty:
    st.warning("Önce müşteri eklemelisiniz!")
  else:
    with st.form("islem_form"):
      secilen_musteri = st.selectbox(
          "Müşteri Seçin", musteriler_df["ad"].tolist()
      )
      musteri_id = musteriler_df[musteriler_df["ad"] == secilen_musteri][
          "id"
      ].values[0]

      islem_turu = st.selectbox(
          "İşlem Türü",
          ["Borç (Satış / Mal Verildi)", "Ödeme (Tahsilat / Para Alındı)"],
      )
      tutar = st.number_input("Tutar (₺)", min_value=0.0, format="%.2f")
      aciklama = st.text_input("Açıklama (Örn: 10 koli ürün / Nakit ödendi)")
      tarih = st.date_input("İşlem Tarihi", datetime.now())

      submit_islem = st.form_submit_button("İşlemi Kaydet")

      if submit_islem:
        cursor = conn.cursor()
        cursor.execute(
            """
                    INSERT INTO hareketler (musteri_id, tarih, islem_turu, tutar, aciklama)
                    VALUES (?, ?, ?, ?, ?)
                """,
            (musteri_id, str(tarih), islem_turu, tutar, aciklama),
        )
        conn.commit()
        conn.close()
        st.success("İşlem başarıyla kaydedildi!")
  conn.close()

# --- 4. TÜM RAPORLAR (EXCEL) ---
elif menu == "Tüm Raporlar (Excel)":
  st.header("📊 Toplu Excel Raporları")
  st.write(
      "Tüm müşteri cari hareketlerini tek bir Excel dosyası olarak"
      " indirebilirsiniz."
  )

  if st.button("Excel Raporu Oluştur"):
    conn = sqlite3.connect(DB_NAME)
    query = """
            SELECT m.ad AS Musteri, m.telefon AS Telefon, h.tarih AS Tarih, 
                   h.islem_turu AS IslemTuru, h.tutar AS Tutar, h.aciklama AS Aciklama
            FROM hareketler h
            JOIN musteriler m ON h.musteri_id = m.id
        """
    df_all = pd.read_sql_query(query, conn)
    conn.close()

    if not df_all.empty:
      output = io.BytesIO()
      with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_all.to_excel(writer, index=False, sheet_name="Cari Raporu")
      output.seek(0)

      st.download_button(
          label="📥 Excel Dosyasını İndir (.xlsx)",
          data=output,
          file_name=f"cari_rapor_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      )
    else:
      st.info("Raporlanacak veri bulunamadı.")