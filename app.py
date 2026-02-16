# ---------------------------------------------------------
# Progetto: Ottimizzatore Trasporti Logistico Puglia & Basilicata
# Autore:   Mirko Giovinazzo, Vito Manzari
# Versione: 4.2
# Copyright © 2026 Tutti i diritti riservati.
# ---------------------------------------------------------
import streamlit as st
import osmnx as ox
import networkx as nx
import pandas as pd

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Gestione Trasporti v4.2", layout="wide")
st.title("🚚 Gestione Trasporti e Smaltimento v4.2")
st.caption("Copyright © 2026 VMMG")
st.divider()

# --- 1. DATABASE DISCARICHE FISSE ---
# Aggiungi qui tutte le discariche che vuoi. Basta seguire il formato.
DISCARICHE_FISSE = [
    {"id": "AMB", "lat": 41.09647057134329, "lon": 16.738474937175116},
    {"id": "NET", "lat": 41.089966857437396, "lon": 16.806883067859623},
    {"id": "DIM", "lat": 41.097295471343244, "lon": 16.91459969669557},
    {"id": "APU", "lat": 40.99342696525014, "lon": 16.783615667855507},
    {"id": "MTL", "lat": 41.04061857135102, "lon": 16.863863967857515}
]

@st.cache_resource
def carica_mappa():
    return ox.load_graphml("mappa_sud_final.graphml")

G = carica_mappa()

# Inizializziamo le tappe con le discariche fisse se la lista è vuota
if 'tappe_clienti' not in st.session_state:
    st.session_state.tappe_clienti = []

# --- SIDEBAR: INSERIMENTO CLIENTI ---
st.sidebar.header("📍 Inserimento Clienti")

# Usiamo un form con clear_on_submit=True
with st.sidebar.form("form_inserimento", clear_on_submit=True):
    seriale = st.text_input("Nome/ID Cliente")
    coord = st.text_input("Coordinate Cliente (Lat, Lon)")
    btn_aggiungi = st.form_submit_button("➕ Aggiungi Cliente")

    if btn_aggiungi:
        if seriale and coord:
            try:
                lat, lon = map(float, coord.replace(" ", "").split(","))
                st.session_state.tappe_clienti.append({
                    "id": seriale, 
                    "lat": lat, 
                    "lon": lon, 
                    "tipo": "Cliente"
                })
                st.sidebar.success(f"Cliente {seriale} aggiunto!")
                # Nota: qui non serve st.rerun(), il form pulisce tutto da solo
            except:
                st.sidebar.error("Errore formato coordinate!")
        else:
            st.sidebar.warning("Inserisci tutti i dati!")

if st.sidebar.button("🗑️ Svuota Lista Clienti"):
    st.session_state.tappe_clienti = []
    st.rerun()

# --- LOGICA DI SELEZIONE ---
if st.session_state.tappe_clienti or DISCARICHE_FISSE:
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👥 Clienti del giorno")
        if st.session_state.tappe_clienti:
            df_c = pd.DataFrame(st.session_state.tappe_clienti)
            st.table(df_c[['ID']])
            urgenti = st.multiselect("Segna URGENTI:", options=df_c['id'].tolist())
        else:
            st.info("Nessun cliente inserito.")
            urgenti = []

    with col2:
        st.subheader("🏭 Destinazione Smaltimento")
        # Menu a tendina con le discariche salvate nel codice
        nomi_discariche = [d['id'] for d in DISCARICHE_FISSE]
        discarica_scelta_id = st.selectbox("Seleziona la DISCARICA per questo viaggio:", options=nomi_discariche)

    # --- CALCOLO PERCORSO ---
    if st.button("🚀 GENERA PERCORSO OTTIMIZZATO"):
        if not st.session_state.tappe_clienti:
            st.warning("Inserisci almeno un cliente!")
        else:
            with st.spinner("Calcolo in corso..."):
                # Magazzino
                partenza_gps = (40.88662985769151, 16.852016478389977)
                nodo_attuale = ox.distance.nearest_nodes(G, partenza_gps[1], partenza_gps[0])
                
                # Dati Discarica Scelta
                d_info = next(d for d in DISCARICHE_FISSE if d['id'] == discarica_scelta_id)
                nodo_discarica = ox.distance.nearest_nodes(G, d_info['lon'], d_info['lat'])

                # Prepariamo i nodi clienti
                clienti_lavoro = []
                for c in st.session_state.tappe_clienti:
                    n = ox.distance.nearest_nodes(G, c['lon'], c['lat'])
                    clienti_lavoro.append((n, c['id'], c['id'] in urgenti))

                percorso_finale = []
                km_totali = 0

                # 1. Urgenti
                urgenti_lavoro = [c for c in clienti_lavoro if c[2]]
                while urgenti_lavoro:
                    prossimo = min(urgenti_lavoro, key=lambda x: nx.shortest_path_length(G, nodo_attuale, x[0], weight='length'))
                    dist = nx.shortest_path_length(G, nodo_attuale, prossimo[0], weight='length')
                    km_totali += dist
                    nodo_attuale = prossimo[0]
                    percorso_finale.append({"Punto": prossimo[1], "Tipo": "RITIRO URGENTE"})
                    urgenti_lavoro.remove(prossimo)

                # 2. Standard (verso la discarica)
                standard_lavoro = [c for c in clienti_lavoro if not c[2]]
                while standard_lavoro:
                    prossimo = min(standard_lavoro, key=lambda x: nx.shortest_path_length(G, nodo_attuale, x[0], weight='length'))
                    dist = nx.shortest_path_length(G, nodo_attuale, prossimo[0], weight='length')
                    km_totali += dist
                    nodo_attuale = prossimo[0]
                    percorso_finale.append({"Punto": prossimo[1], "Tipo": "RITIRO"})
                    standard_lavoro.remove(prossimo)

                # 3. Chiusura in Discarica
                dist_f = nx.shortest_path_length(G, nodo_attuale, nodo_discarica, weight='length')
                km_totali += dist_f
                percorso_finale.append({"Punto": discarica_scelta_id, "Tipo": "SCARICO FINALE"})

                st.success(f"✅ Percorso ottimizzato verso {discarica_scelta_id}: {km_totali/1000:.2f} km")
                st.table(percorso_finale)

                st.markdown("<br><hr><center>Copyright © 2026 VMMG</center>", unsafe_allow_html=True)