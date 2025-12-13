import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import uuid
import gspread

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Gestore Finanze Cloud", layout="wide", page_icon="☁️")

# --- 2. CONNESSIONE DIRETTA DA FILE (Metodo Infallibile Locale) ---
def connetti_google_sheet():
    try:
        # Cerchiamo il file credentials.json nella cartella
        # Se siamo in locale userà questo, se siamo online userà i secrets (opzionale, ma ora concentriamoci sul PC)
        filename = "credentials.json"
        
        # Questa funzione di gspread legge direttamente il file JSON fisico
        # Bypassa qualsiasi errore di conversione di Streamlit
        client = gspread.service_account(filename=filename)
        
        sheet = client.open("GestioneSpese").sheet1 
        return sheet
        
    except FileNotFoundError:
        st.error("⚠️ File 'credentials.json' non trovato! Assicurati di averlo creato nella cartella Spese.")
        st.stop()
    except Exception as e:
        st.error(f"⚠️ Errore critico connessione: {e}")
        st.stop()

def genera_id():
    return str(uuid.uuid4())[:8]

def carica_dati():
    cols = ["ID", "Data", "Tipo", "Categoria", "Importo", "Note"]
    df = pd.DataFrame(columns=cols) 
    
    try:
        sheet = connetti_google_sheet()
        
        if not sheet.get_all_values():
            sheet.append_row(cols)
            return df

        data = sheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            
    except Exception as e:
        st.warning(f"Avvio con database vuoto. ({e})")

    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors='coerce')
        df = df.dropna(subset=["Data"])
        
    return df

def salva_dati_su_cloud(df):
    try:
        sheet = connetti_google_sheet()
        df_export = df.copy()
        df_export["Data"] = df_export["Data"].dt.strftime('%Y-%m-%d')
        dati_completi = [df_export.columns.values.tolist()] + df_export.values.tolist()
        
        sheet.clear()
        sheet.update(range_name='A1', values=dati_completi)
        return True
    except Exception as e:
        st.error(f"Errore salvataggio Cloud: {e}")
        return False

# --- 3. APP ---
df = carica_dati()

st.sidebar.title("☁️ Comandi")
st.sidebar.subheader("➕ Aggiungi")

with st.sidebar.form("form_inserimento", clear_on_submit=True):
    data_input = st.date_input("Data", datetime.date.today())
    tipo_input = st.selectbox("Tipo", ["Uscita", "Entrata"])
    
    if tipo_input == "Uscita":
        cat_list = ["Cibo", "Casa", "Trasporti", "Salute", "Svago", "Shopping", "Bollette", "Altro"]
    else:
        cat_list = ["Stipendio", "Bonus", "Vendite", "Rimborsi", "Investimenti", "Altro"]
        
    categoria_input = st.selectbox("Categoria", cat_list)
    importo_input = st.number_input("Importo (€)", min_value=0.0, format="%.2f")
    note_input = st.text_input("Note")
    
    if st.form_submit_button("Salva"):
        nuovo_record = pd.DataFrame({
            "ID": [genera_id()],
            "Data": [pd.to_datetime(data_input)],
            "Tipo": [tipo_input],
            "Categoria": [categoria_input],
            "Importo": [importo_input],
            "Note": [note_input]
        })
        
        df = pd.concat([df, nuovo_record], ignore_index=True) if not df.empty else nuovo_record
        
        with st.spinner("Salvataggio..."):
            if salva_dati_su_cloud(df):
                st.success("Salvato!")
                st.rerun()

st.sidebar.markdown("---")
anno_corrente = datetime.date.today().year
if not df.empty and "Data" in df.columns:
    try:
        anni_dal_db = df["Data"].dt.year.dropna().astype(int).unique().tolist()
    except: anni_dal_db = []
else: anni_dal_db = []

anno_selezionato = st.sidebar.selectbox("Anno", sorted(list(set(anni_dal_db + [anno_corrente])), reverse=True))

if not df.empty:
    df_filtrato = df[df["Data"].dt.year == anno_selezionato]
else:
    df_filtrato = pd.DataFrame(columns=df.columns)

st.title(f"📊 Dashboard {anno_selezionato}")

if not df_filtrato.empty:
    entrate = df_filtrato[df_filtrato["Tipo"] == "Entrata"]["Importo"].sum()
    uscite = df_filtrato[df_filtrato["Tipo"] == "Uscita"]["Importo"].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Entrate", f"€ {entrate:,.2f}")
    c2.metric("Uscite", f"€ {uscite:,.2f}")
    c3.metric("Saldo", f"€ {entrate-uscite:,.2f}")
    
    st.plotly_chart(px.bar(df_filtrato, x="Data", y="Importo", color="Tipo", title="Trend", color_discrete_map={"Entrata": "#00CC96", "Uscita": "#EF553B"}), use_container_width=True)

    st.subheader("📝 Modifica")
    df_modificato = st.data_editor(df_filtrato, num_rows="dynamic", hide_index=True, key="editor")

    if st.button("💾 Salva Modifiche"):
        df_db = carica_dati()
        ids_visualizzati = df_filtrato["ID"].tolist()
        df_db = df_db[~df_db["ID"].isin(ids_visualizzati)]
        
        for i, row in df_modificato.iterrows():
            if pd.isna(row["ID"]) or row["ID"] == "": df_modificato.at[i, "ID"] = genera_id()
            
        df_finale = pd.concat([df_db, df_modificato], ignore_index=True)
        if salva_dati_su_cloud(df_finale):
            st.success("Fatto!")
            st.rerun()
else:
    st.info("Nessun dato.")
