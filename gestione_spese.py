import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import uuid
import gspread

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Gestore Finanze Cloud", layout="wide", page_icon="☁️")

# --- 2. CONNESSIONE A GOOGLE SHEETS (METODO SEMPLIFICATO) ---
def connetti_google_sheet():
    """
    Stabilisce la connessione usando il metodo nativo di gspread.
    Questo evita l'errore <Response [200]> gestendo le credenziali internamente.
    """
    try:
        # Recuperiamo il dizionario delle credenziali dai secrets
        # Streamlit converte automaticamente il TOML in un dizionario Python
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # Questa funzione fa tutto da sola: autenticazione e scope corretti
        client = gspread.service_account_from_dict(creds_dict)
        
        # Apriamo il foglio di lavoro
        sheet = client.open("GestioneSpese").sheet1 
        return sheet
        
    except Exception as e:
        st.error(f"⚠️ Errore critico connessione: {e}")
        st.stop()

def genera_id():
    """Genera un codice univoco breve"""
    return str(uuid.uuid4())[:8]

def carica_dati():
    """
    Scarica i dati e gestisce date e formati per evitare crash.
    """
    cols = ["ID", "Data", "Tipo", "Categoria", "Importo", "Note"]
    df = pd.DataFrame(columns=cols) 
    
    try:
        sheet = connetti_google_sheet()
        
        # Se il foglio è vuoto, scriviamo le intestazioni
        if not sheet.get_all_values():
            sheet.append_row(cols)
            return df

        # Scarichiamo i dati
        data = sheet.get_all_records()
        
        if data:
            df = pd.DataFrame(data)
            
    except Exception as e:
        st.warning(f"Impossibile leggere i dati online. Avvio con database vuoto. ({e})")

    # --- PROTEZIONE CRASH DATE ---
    if "Data" in df.columns:
        # errors='coerce' trasforma le date sbagliate in NaT (null) invece di bloccare l'app
        df["Data"] = pd.to_datetime(df["Data"], errors='coerce')
        # Rimuove righe con date non valide
        df = df.dropna(subset=["Data"])
        
    return df

def salva_dati_su_cloud(df):
    """
    Salva i dati su Google Sheets convertendo le date in stringhe.
    """
    try:
        sheet = connetti_google_sheet()
        
        df_export = df.copy()
        # Convertiamo datetime in stringa YYYY-MM-DD per Google Sheets
        df_export["Data"] = df_export["Data"].dt.strftime('%Y-%m-%d')
        
        # Prepariamo la griglia completa (Intestazioni + Dati)
        dati_completi = [df_export.columns.values.tolist()] + df_export.values.tolist()
        
        sheet.clear()
        sheet.update(range_name='A1', values=dati_completi)
        return True
    except Exception as e:
        st.error(f"Errore salvataggio Cloud: {e}")
        return False

# --- 3. LOGICA APPLICAZIONE ---
df = carica_dati()

# --- SIDEBAR: INSERIMENTO ---
st.sidebar.title("☁️ Comandi")
st.sidebar.subheader("➕ Aggiungi Movimento")

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
    
    btn_aggiungi = st.form_submit_button("Aggiungi e Salva")

    if btn_aggiungi:
        nuovo_record = pd.DataFrame({
            "ID": [genera_id()],
            "Data": [pd.to_datetime(data_input)],
            "Tipo": [tipo_input],
            "Categoria": [categoria_input],
            "Importo": [importo_input],
            "Note": [note_input]
        })
        
        if df.empty:
            df = nuovo_record
        else:
            df = pd.concat([df, nuovo_record], ignore_index=True)
        
        with st.spinner("Salvataggio su Google Sheets in corso..."):
            if salva_dati_su_cloud(df):
                st.success("Salvato online!")
                st.rerun()

st.sidebar.markdown("---")

# --- SIDEBAR: FILTRI ---
st.sidebar.subheader("📅 Filtra Periodo")
anno_corrente = datetime.date.today().year

# Calcolo anni disponibili sicuro
if not df.empty and "Data" in df.columns:
    try:
        anni_dal_db = df["Data"].dt.year.dropna().astype(int).unique().tolist()
    except:
        anni_dal_db = []
else:
    anni_dal_db = []

anni_totali = sorted(list(set(anni_dal_db + [anno_corrente])), reverse=True)
anno_selezionato = st.sidebar.selectbox("Anno", anni_totali)

mesi_dict = {1:"Gennaio", 2:"Febbraio", 3:"Marzo", 4:"Aprile", 5:"Maggio", 6:"Giugno", 
             7:"Luglio", 8:"Agosto", 9:"Settembre", 10:"Ottobre", 11:"Novembre", 12:"Dicembre"}
mese_selezionato = st.sidebar.selectbox("Mese", ["Tutti"] + list(mesi_dict.values()))

# Applicazione Filtri
if not df.empty:
    df_filtrato = df[df["Data"].dt.year == anno_selezionato]
    if mese_selezionato != "Tutti":
        mese_num = list(mesi_dict.keys())[list(mesi_dict.values()).index(mese_selezionato)]
        df_filtrato = df_filtrato[df_filtrato["Data"].dt.month == mese_num]
else:
    df_filtrato = pd.DataFrame(columns=df.columns)

# --- DASHBOARD ---
st.title(f"📊 Dashboard - {mese_selezionato} {anno_selezionato}")

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
        fig_bar = px.bar(df_filtrato, x="Data", y="Importo", color="Tipo", title="Andamento", 
                         color_discrete_map={"Entrata": "#00CC96", "Uscita": "#EF553B"})
        st.plotly_chart(fig_bar, use_container_width=True)
    with c2:
        df_pie = df_filtrato[df_filtrato["Tipo"] == "Uscita"]
        if not df_pie.empty:
            fig_pie = px.pie(df_pie, values="Importo", names="Categoria", hole=0.4, title="Spese")
            st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")
    st.subheader("📝 Modifica Dati")
    
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
        with st.spinner("Sincronizzazione..."):
            df_db_completo = carica_dati()
            ids_visualizzati = df_filtrato["ID"].tolist()
            df_db_aggiornato = df_db_completo[~df_db_completo["ID"].isin(ids_visualizzati)]
            
            for index, row in df_modificato.iterrows():
                if pd.isna(row["ID"]) or row["ID"] == "":
                    df_modificato.at[index, "ID"] = genera_id()
            
            df_finale = pd.concat([df_db_aggiornato, df_modificato], ignore_index=True)
            
            if salva_dati_su_cloud(df_finale):
                st.success("Fatto!")
                st.rerun()
else:
    st.info("Nessun dato per questo periodo.")
