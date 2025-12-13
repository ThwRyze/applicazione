import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import uuid
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Gestore Finanze Cloud", layout="wide", page_icon="☁️")

# --- 2. CONNESSIONE A GOOGLE SHEETS (METODO SICURO) ---
def connetti_google_sheet():
    """
    Stabilisce la connessione con Google Sheets usando le credenziali nei Secrets.
    """
    try:
        # Definiamo i permessi necessari
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Carichiamo le credenziali dal file secrets.toml (locale o cloud)
        creds_dict = st.secrets["gcp_service_account"]
        
        # Creiamo l'oggetto credenziali
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        
        # Autorizziamo il client
        client = gspread.authorize(creds)
        
        # Apriamo il foglio di lavoro
        sheet = client.open("GestioneSpese").sheet1 
        return sheet
        
    except Exception as e:
        # In caso di errore (es. secrets mancanti), fermiamo l'esecuzione con un messaggio chiaro
        st.error(f"⚠️ Errore di connessione a Google Sheets. Controlla il file secrets.toml o i permessi del foglio.\n\nDettaglio errore: {e}")
        st.stop()

def genera_id():
    """Genera un codice univoco breve per ogni transazione"""
    return str(uuid.uuid4())[:8]

def carica_dati():
    """
    Scarica i dati da Google Sheets e li converte in un DataFrame Pandas.
    Gestisce casi di foglio vuoto o errori di formato.
    """
    # Struttura base del database
    cols = ["ID", "Data", "Tipo", "Categoria", "Importo", "Note"]
    df = pd.DataFrame(columns=cols) # DataFrame vuoto di default
    
    try:
        sheet = connetti_google_sheet()
        
        # Se il foglio è completamente vuoto, scriviamo le intestazioni
        if not sheet.get_all_values():
            sheet.append_row(cols)
            return df # Ritorniamo il df vuoto ma con le colonne giuste

        # Scarichiamo i dati
        data = sheet.get_all_records()
        
        # Se ci sono dati, aggiorniamo il DataFrame
        if data:
            df = pd.DataFrame(data)
            
    except Exception as e:
        st.warning(f"Impossibile leggere i dati online. Avvio con database vuoto locale. ({e})")

    # --- CORREZIONE CRITICA PER EVITARE CRASH ---
    # Forziamo la conversione della colonna Data in datetime.
    # 'coerce' trasforma eventuali errori in NaT (Not a Time) invece di bloccare tutto.
    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors='coerce')
        # Rimuoviamo righe dove la data non è valida (pulizia dati sporchi)
        df = df.dropna(subset=["Data"])
        
    return df

def salva_dati_su_cloud(df):
    """
    Sovrascrive il foglio Google con i dati attuali del DataFrame.
    """
    try:
        sheet = connetti_google_sheet()
        
        # Creiamo una copia per l'export (convertendo le date in stringhe leggibili)
        df_export = df.copy()
        df_export["Data"] = df_export["Data"].dt.strftime('%Y-%m-%d')
        
        # Prepariamo la lista di liste (Intestazioni + Dati)
        dati_completi = [df_export.columns.values.tolist()] + df_export.values.tolist()
        
        # Puliamo e riscriviamo
        sheet.clear()
        sheet.update(range_name='A1', values=dati_completi)
        return True
    except Exception as e:
        st.error(f"Errore salvataggio Cloud: {e}")
        return False

# --- 3. CARICAMENTO DATI INIZIALE ---
df = carica_dati()

# --- 4. SIDEBAR: INSERIMENTO DATI ---
st.sidebar.title("☁️ Comandi")
st.sidebar.subheader("➕ Aggiungi Movimento")

with st.sidebar.form("form_inserimento", clear_on_submit=True):
    data_input = st.date_input("Data", datetime.date.today())
    tipo_input = st.selectbox("Tipo", ["Uscita", "Entrata"])
    
    # Liste categorie dinamiche
    if tipo_input == "Uscita":
        cat_list = ["Cibo", "Casa", "Trasporti", "Salute", "Svago", "Shopping", "Bollette", "Altro"]
    else:
        cat_list = ["Stipendio", "Bonus", "Vendite", "Rimborsi", "Investimenti", "Altro"]
        
    categoria_input = st.selectbox("Categoria", cat_list)
    importo_input = st.number_input("Importo (€)", min_value=0.0, format="%.2f")
    note_input = st.text_input("Note (Opzionale)")
    
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
        
        # Concatenazione sicura
        if df.empty:
            df = nuovo_record
        else:
            df = pd.concat([df, nuovo_record], ignore_index=True)
        
        with st.spinner("Salvataggio su Google Sheets in corso..."):
            if salva_dati_su_cloud(df):
                st.success("Salvato online!")
                st.rerun()

st.sidebar.markdown("---")

# --- 5. SIDEBAR: FILTRI ---
st.sidebar.subheader("📅 Filtra Periodo")
anno_corrente = datetime.date.today().year

# Logica per trovare gli anni disponibili senza crashare
if not df.empty and "Data" in df.columns:
    try:
        anni_dal_db = df["Data"].dt.year.dropna().astype(int).unique().tolist()
    except:
        anni_dal_db = []
else:
    anni_dal_db = []

# Uniamo anno corrente agli anni del DB
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

# --- 6. DASHBOARD PRINCIPALE ---
st.title(f"📊 Dashboard - {mese_selezionato} {anno_selezionato}")

if not df_filtrato.empty:
    # --- KPI ---
    entrate = df_filtrato[df_filtrato["Tipo"] == "Entrata"]["Importo"].sum()
    uscite = df_filtrato[df_filtrato["Tipo"] == "Uscita"]["Importo"].sum()
    saldo = entrate - uscite

    col1, col2, col3 = st.columns(3)
    col1.metric("Entrate", f"€ {entrate:,.2f}")
    col2.metric("Uscite", f"€ {uscite:,.2f}")
    col3.metric("Saldo", f"€ {saldo:,.2f}", delta_color="normal")
    st.markdown("---")

    # --- GRAFICI ---
    c1, c2 = st.columns([2, 1])
    
    with c1:
        # Grafico a Barre (Trend)
        fig_bar = px.bar(df_filtrato, x="Data", y="Importo", color="Tipo", title="Andamento Temporale", 
                         color_discrete_map={"Entrata": "#00CC96", "Uscita": "#EF553B"},
                         hover_data=["Categoria", "Note"])
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with c2:
        # Grafico a Torta (Solo uscite)
        df_pie = df_filtrato[df_filtrato["Tipo"] == "Uscita"]
        if not df_pie.empty:
            fig_pie = px.pie(df_pie, values="Importo", names="Categoria", hole=0.4, title="Ripartizione Spese")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Nessuna uscita da mostrare nel grafico.")

    st.markdown("---")
    
    # --- MODIFICA E CANCELLAZIONE ---
    st.subheader("📝 Gestione Dati")
    st.info("Modifica le celle e premi 'Salva Modifiche'. Per eliminare righe: selezionale a sinistra e premi CANC.")
    
    df_modificato = st.data_editor(
        df_filtrato,
        column_config={
            "ID": None, # Nasconde ID
            "Importo": st.column_config.NumberColumn(format="€ %.2f"),
            "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Tipo": st.column_config.SelectboxColumn(options=["Entrata", "Uscita"]),
            "Categoria": st.column_config.SelectboxColumn(options=["Cibo", "Casa", "Trasporti", "Salute", "Svago", "Shopping", "Bollette", "Altro", "Stipendio", "Bonus", "Vendite"]),
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="editor_cloud"
    )

    if st.button("💾 Salva Modifiche su Cloud", type="primary"):
        with st.spinner("Sincronizzazione con Google Sheets..."):
            # 1. Ricarichiamo il DB completo aggiornato
            df_db_completo = carica_dati()
            
            # 2. Rimuoviamo le righe vecchie (quelle che stiamo visualizzando e potenzialmente modificando)
            ids_visualizzati = df_filtrato["ID"].tolist()
            df_db_aggiornato = df_db_completo[~df_db_completo["ID"].isin(ids_visualizzati)]
            
            # 3. Assegniamo ID alle nuove righe inserite dall'editor
            for index, row in df_modificato.iterrows():
                if pd.isna(row["ID"]) or row["ID"] == "":
                    df_modificato.at[index, "ID"] = genera_id()
            
            # 4. Uniamo tutto
            df_finale = pd.concat([df_db_aggiornato, df_modificato], ignore_index=True)
            
            # 5. Salviamo
            if salva_dati_su_cloud(df_finale):
                st.success("Database aggiornato con successo!")
                st.rerun()
else:
    st.info("Nessun dato trovato per il periodo selezionato. Usa la barra laterale per aggiungere spese!")
