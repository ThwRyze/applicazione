import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import uuid
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Configurazione Pagina ---
st.set_page_config(page_title="Gestore Finanze Cloud", layout="wide", page_icon="☁️")

# --- CONNESSIONE A GOOGLE SHEETS ---
# Questa funzione gestisce la connessione sicura usando i "Secrets" di Streamlit
def connetti_google_sheet():
    # Definiamo i permessi necessari
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Recuperiamo le credenziali dai segreti di Streamlit (funziona sia in locale che online)
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Apre il foglio usando il nome o la chiave (Usa l'URL o il nome esatto del file su Drive)
    # IMPORTANTE: Assicurati che il nome qui sotto sia ESATTO come su Google Drive
    sheet = client.open("GestioneSpese").sheet1 
    return sheet

def genera_id():
    return str(uuid.uuid4())[:8]

def carica_dati():
    try:
        sheet = connetti_google_sheet()
        # Scarica tutti i dati e li mette in un DataFrame
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Se il foglio è vuoto (ha solo le intestazioni), crea un df vuoto ma con le colonne giuste
        if df.empty:
            return pd.DataFrame(columns=["ID", "Data", "Tipo", "Categoria", "Importo", "Note"])
            
        df["Data"] = pd.to_datetime(df["Data"])
        return df
    except Exception as e:
        st.error(f"Errore di connessione a Google Sheets: {e}")
        return pd.DataFrame(columns=["ID", "Data", "Tipo", "Categoria", "Importo", "Note"])

def salva_dati_su_cloud(df):
    try:
        sheet = connetti_google_sheet()
        
        # Convertiamo le date in stringhe per Google Sheets
        df_export = df.copy()
        df_export["Data"] = df_export["Data"].dt.strftime('%Y-%m-%d')
        
        # Sostituiamo tutto il contenuto del foglio
        # 1. Aggiorna intestazioni
        sheet.update([df_export.columns.values.tolist()] + df_export.values.tolist())
        return True
    except Exception as e:
        st.error(f"Errore salvataggio Cloud: {e}")
        return False

# Caricamento iniziale
df = carica_dati()

# --- SIDEBAR: Inserimento ---
st.sidebar.title("☁️ Comandi Cloud")
st.sidebar.subheader("➕ Nuovo Movimento")

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
    
    btn_aggiungi = st.form_submit_button("Aggiungi e Salva Online")

    if btn_aggiungi:
        nuovo_record = pd.DataFrame({
            "ID": [genera_id()],
            "Data": [pd.to_datetime(data_input)],
            "Tipo": [tipo_input],
            "Categoria": [categoria_input],
            "Importo": [importo_input],
            "Note": [note_input]
        })
        df = pd.concat([df, nuovo_record], ignore_index=True)
        
        with st.spinner("Salvataggio su Google Sheets in corso..."):
            if salva_dati_su_cloud(df):
                st.success("Salvato online!")
                st.rerun()

st.sidebar.markdown("---")

# --- SIDEBAR: Filtri ---
st.sidebar.subheader("📅 Filtra Dati")
anno_corrente = datetime.date.today().year
if not df.empty:
    anni_dal_db = df["Data"].dt.year.dropna().astype(int).unique().tolist()
else:
    anni_dal_db = []
anni_totali = sorted(list(set(anni_dal_db + [anno_corrente])), reverse=True)
anno_selezionato = st.sidebar.selectbox("Anno", anni_totali)

mesi_dict = {1:"Gennaio", 2:"Febbraio", 3:"Marzo", 4:"Aprile", 5:"Maggio", 6:"Giugno", 
             7:"Luglio", 8:"Agosto", 9:"Settembre", 10:"Ottobre", 11:"Novembre", 12:"Dicembre"}
mese_selezionato = st.sidebar.selectbox("Mese", ["Tutti"] + list(mesi_dict.values()))

# Filtri
df_filtrato = df[df["Data"].dt.year == anno_selezionato]
if mese_selezionato != "Tutti":
    mese_num = list(mesi_dict.keys())[list(mesi_dict.values()).index(mese_selezionato)]
    df_filtrato = df_filtrato[df_filtrato["Data"].dt.month == mese_num]

# --- DASHBOARD ---
st.title(f"📊 Dashboard Cloud - {mese_selezionato} {anno_selezionato}")

if not df_filtrato.empty:
    entrate = df_filtrato[df_filtrato["Tipo"] == "Entrata"]["Importo"].sum()
    uscite = df_filtrato[df_filtrato["Tipo"] == "Uscita"]["Importo"].sum()
    saldo = entrate - uscite

    col1, col2, col3 = st.columns(3)
    col1.metric("Entrate", f"€ {entrate:,.2f}")
    col2.metric("Uscite", f"€ {uscite:,.2f}")
    col3.metric("Saldo", f"€ {saldo:,.2f}", delta_color="normal")
    st.markdown("---")

    c1, c2 = st.columns([2, 1])
    with c1:
        st.plotly_chart(px.bar(df_filtrato, x="Data", y="Importo", color="Tipo", title="Trend", 
                       color_discrete_map={"Entrata": "#00CC96", "Uscita": "#EF553B"}), use_container_width=True)
    with c2:
        df_pie = df_filtrato[df_filtrato["Tipo"] == "Uscita"]
        if not df_pie.empty:
            st.plotly_chart(px.pie(df_pie, values="Importo", names="Categoria", hole=0.4, title="Spese"), use_container_width=True)

    st.markdown("---")
    st.subheader("📝 Modifica / Cancella")
    
    df_modificato = st.data_editor(
        df_filtrato,
        column_config={
            "ID": None,
            "Importo": st.column_config.NumberColumn(format="€ %.2f"),
            "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Tipo": st.column_config.SelectboxColumn(options=["Entrata", "Uscita"]),
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="editor_cloud"
    )

    if st.button("💾 Salva Modifiche su Cloud", type="primary"):
        with st.spinner("Sincronizzazione con Google..."):
            df_db_completo = carica_dati()
            ids_da_rimuovere = df_filtrato["ID"].tolist()
            df_db_aggiornato = df_db_completo[~df_db_completo["ID"].isin(ids_da_rimuovere)]
            
            for index, row in df_modificato.iterrows():
                if pd.isna(row["ID"]) or row["ID"] == "":
                    df_modificato.at[index, "ID"] = genera_id()
            
            df_finale = pd.concat([df_db_aggiornato, df_modificato], ignore_index=True)
            
            if salva_dati_su_cloud(df_finale):
                st.success("Google Sheets aggiornato!")
                st.rerun()
else:
    st.info("Nessun dato.")