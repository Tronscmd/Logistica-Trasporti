import streamlit as st
import osmnx as ox
import networkx as nx
import pandas as pd

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Ottimizzatore Sud v4.2", page_icon="🚚", layout="wide")

st.title("🚚 Sistema Logistico Puglia/Basilicata v4.2")
st.markdown("Copyright © 2026 - Creato da VMMG")
st.divider()

# --- CARICAMENTO MAPPA ---
@st.cache_resource
def carica_mappa():
    try:
        # Carichiamo il file rifinito da 96MB
        return ox.load_graphml("mappa_sud_final.graphml")
    except Exception as e:
        st.error(f"❌ Errore nel caricamento mappa: {e}")
        return None

G = carica_mappa()

if G is None:
    st.info("Assicurati che il file 'mappa_sud_final.graphml' sia nella cartella principale di GitHub.")
    st.stop()

# --- GESTIONE STATO APPLICAZIONE ---
if 'tappe' not in st.session_state:
    st.session_state.tappe = []

# --- SIDEBAR: INSERIMENTO DATI ---
st.sidebar.header("📍 Inserimento Clienti")
with st.sidebar.form("input_form", clear_on_submit=True):
    seriale = st.text_input("Seriale Cliente")
    coord_raw = st.text_input("Coordinate (lat, lon)")
    submit = st.form_submit_button("➕ Aggiungi Tappa")

    if submit:
        if seriale and coord_raw:
            try:
                pulito = coord_raw.replace(" ", "").replace("(", "").replace(")", "")
                lat, lon = map(float, pulito.split(","))
                st.session_state.tappe.append({"seriale": seriale, "lat": lat, "lon": lon})
                st.success(f"Tappa {seriale} aggiunta!")
            except:
                st.error("Formato coordinate errato! Usa: lat, lon")
        else:
            st.warning("Inserisci sia seriale che coordinate.")

if st.sidebar.button("🗑️ Svuota tutto"):
    st.session_state.tappe = []
    st.rerun()

# --- LOGICA PRINCIPALE ---
if st.session_state.tappe:
    st.subheader("📋 Tappe Inserite")
    df = pd.DataFrame(st.session_state.tappe)
    st.dataframe(df, use_container_width=True)
    
    # 1. Selezione Urgenze
    urgenti_nomi = st.multiselect(
        "Seleziona i clienti URGENTI (se presenti):", 
        options=[t['seriale'] for t in st.session_state.tappe]
    )
    
    # 2. Scelta Modalità
    modalita = st.radio("Modalità Operativa:", ["Standard (Percorso Breve)", "Gestione URGENZE"])
    
    scelta_inizio = None
    if modalita == "Gestione URGENZE" and urgenti_nomi:
        scelta_inizio = st.selectbox(
            "🎯 Da quale cliente urgente vuoi iniziare il giro?", 
            options=urgenti_nomi
        )

    # 3. Pulsante di Calcolo
    if st.button("🚀 CALCOLA PERCORSO OTTIMALE"):
        with st.spinner("Calcolo del percorso migliore in corso..."):
            partenza_gps = (40.88662985769151, 16.852016478389977)
            nodo_partenza = ox.distance.nearest_nodes(G, partenza_gps[1], partenza_gps[0])
            
            ordine_finale = [(nodo_partenza, "MAGAZZINO")]
            km_totali = 0
            attuale = nodo_partenza

            def trova_prossimo(lista_nodi, nodo_attuale):
                prossimo_nodo = min(lista_nodi, key=lambda n: nx.shortest_path_length(G, nodo_attuale, n[0], weight='length'))
                distanza = nx.shortest_path_length(G, nodo_attuale, prossimo_nodo[0], weight='length')
                return prossimo_nodo, distanza

            # Prepariamo i nodi
            tappe_lavoro = []
            for t in st.session_state.tappe:
                n = ox.distance.nearest_nodes(G, t['lon'], t['lat'])
                tappe_lavoro.append((n, t['seriale'], t['seriale'] in urgenti_nomi))

            if modalita == "Gestione URGENZE" and scelta_inizio:
                # Separiamo urgenze e standard
                urgenti = [(n, s) for n, s, u in tappe_lavoro if u]
                standard = [(n, s) for n, s, u in tappe_nodi if not u] # Nota: risolto typo qui
                
                # Prendiamo il primo scelto
                primo_tupla = next(item for item in urgenti if item[1] == scelta_inizio)
                urgenti.remove(primo_tupla)
                
                # Magazzino -> Primo Scelto
                dist, d_val = nx.shortest_path_length(G, attuale, primo_tupla[0], weight='length'), nx.shortest_path_length(G, attuale, primo_tupla[0], weight='length')
                km_totali += d_val
                ordine_finale.append(primo_tupla)
                attuale = primo_tupla[0]
                
                # Poi restanti urgenti, poi standard
                for gruppo in [urgenti, [(n, s) for n, s, u in tappe_lavoro if not u]]:
                    while gruppo:
                        prossimo, d = trova_prossimo(gruppo, attuale)
                        km_totali += d
                        ordine_finale.append(prossimo)
                        gruppo.remove(prossimo)
                        attuale = prossimo[0]
            else:
                # Modalità Standard o Urgenze senza selezione specifica
                rimanenti = [(n, s) for n, s, u in tappe_lavoro]
                while rimanenti:
                    prossimo, d = trova_prossimo(rimanenti, attuale)
                    km_totali += d
                    ordine_finale.append(prossimo)
                    rimanenti.remove(prossimo)
                    attuale = prossimo[0]

            # --- RISULTATI ---
            st.divider()
            st.success(f"🏁 Calcolo Completato! Distanza totale: **{km_totali/1000:.2f} km**")
            
            res_list = []
            for i, (nodo, ser) in enumerate(ordine_finale):
                lat, lon = G.nodes[nodo]['y'], G.nodes[nodo]['x']
                res_list.append({"Fermata": i, "Cliente": ser, "Coordinate": f"{lat}, {lon}"})
            
            st.table(res_list)
            
            # Export TXT
            testo_file = "TABELLA DI MARCIA\n" + "="*20 + "\n"
            for r in res_list:
                testo_file += f"STOP {r['Fermata']}: {r['Cliente']} ({r['Coordinate']})\n"
            testo_file += f"\nTotale km: {km_totali/1000:.2f}"
            
            st.download_button("📥 Scarica Percorso (.txt)", testo_file, file_name="percorso_logistica.txt")

else:
    st.info("👋 Benvenuto! Aggiungi i clienti nella barra a sinistra per calcolare il percorso.")