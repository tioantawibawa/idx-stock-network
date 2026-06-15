import streamlit as st
import yfinance as yf
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Konfigurasi Halaman Streamlit
st.set_page_config(page_title="Analisis Jaringan Saham IDX", layout="wide")
st.title("🕸️ Analisis Jaringan Korelasi Saham Indonesia (IDX)")
st.markdown("""
Dashboard ini memvisualisasikan saham-saham yang bergerak searah. 
Garis yang menghubungkan dua saham menunjukkan korelasi positif yang kuat di antara keduanya.
""")

# --- SIDEBAR PENGATURAN ---
st.sidebar.header("Pengaturan Analisis")

# Daftar Saham Default (Bluechips & Tech)
default_tickers = "BBCA.JK, BBRI.JK, BMRI.JK, BBNI.JK, TLKM.JK, ASII.JK, GOTO.JK, AMMN.JK, BREN.JK, UNVR.JK, ICBP.JK, PGAS.JK, ADRO.JK, PTBA.JK"
tickers_input = st.sidebar.text_area("Masukkan Kode Saham (Gunakan .JK untuk saham Indonesia):", default_tickers)
tickers_list = [ticker.strip() for ticker in tickers_input.split(',')]

# Pengaturan Waktu
end_date = datetime.today()
start_date = end_date - timedelta(days=365) # Default 1 tahun terakhir
start = st.sidebar.date_input("Tanggal Mulai", start_date)
end = st.sidebar.date_input("Tanggal Akhir", end_date)

# Batas Korelasi
corr_threshold = st.sidebar.slider("Batas Korelasi Minimum", min_value=0.0, max_value=1.0, value=0.6, step=0.05, 
                                   help="Semakin tinggi nilainya, semakin ketat hubungannya. 0.6 berarti korelasi positif yang cukup kuat.")

# --- MENGAMBIL DATA ---
@st.cache_data
def load_data(tickers, start, end):
    try:
        # Mengunduh harga penutupan yang disesuaikan (Adj Close)
        data = yf.download(tickers, start=start, end=end)['Adj Close']
        # Menghitung persentase perubahan harian (return)
        returns = data.pct_change().dropna()
        # Menghitung matriks korelasi
        corr_matrix = returns.corr()
        return corr_matrix
    except Exception as e:
        return str(e)

with st.spinner("Mengunduh data dan menghitung korelasi..."):
    corr_matrix = load_data(tickers_list, start, end)

if isinstance(corr_matrix, str):
    st.error(f"Terjadi kesalahan saat mengambil data: {corr_matrix}")
else:
    # --- MEMBUAT JARINGAN (NETWORK) ---
    G = nx.Graph()
    
    # Menambahkan Node (Saham)
    for ticker in tickers_list:
        G.add_node(ticker)

    # Menambahkan Edge (Garis Koneksi) berdasarkan Threshold Korelasi
    for i in range(len(corr_matrix.columns)):
        for j in range(i+1, len(corr_matrix.columns)):
            stock1 = corr_matrix.columns[i]
            stock2 = corr_matrix.columns[j]
            korelasi = corr_matrix.iloc[i, j]
            
            if korelasi >= corr_threshold:
                G.add_edge(stock1, stock2, weight=korelasi)

    # --- VISUALISASI DENGAN PLOTLY ---
    # Mengatur tata letak node (menggunakan spring layout agar yang terkoneksi berdekatan)
    pos = nx.spring_layout(G, seed=42)

    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1.5, color='#888'),
        hoverinfo='none',
        mode='lines')

    node_x = []
    node_y = []
    node_text = []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        
        # Hitung jumlah koneksi (derajat node) untuk info hover
        connections = len(list(G.neighbors(node)))
        node_text.append(f"{node}<br>Koneksi: {connections}")

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=[node.replace('.JK', '') for node in G.nodes()], # Menampilkan nama ticker tanpa .JK
        textposition="bottom center",
        hoverinfo='text',
        hovertext=node_text,
        marker=dict(
            showscale=True,
            colorscale='YlGnBu',
            reversescale=True,
            color=[len(list(G.neighbors(node))) for node in G.nodes()],
            size=30,
            colorbar=dict(
                thickness=15,
                title='Jumlah Korelasi',
                xanchor='left',
                titleside='right'
            ),
            line_width=2))

    fig = go.Figure(data=[edge_trace, node_trace],
                 layout=go.Layout(
                    title='<br>Jaringan Korelasi Pergerakan Saham',
                    titlefont_size=16,
                    showlegend=False,
                    hovermode='closest',
                    margin=dict(b=20,l=5,r=5,t=40),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                 )

    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("""
    **Cara Membaca:**
    * **Titik (Node):** Mewakili satu saham. Semakin gelap/berbeda warnanya, semakin banyak saham lain yang berkorelasi dengannya.
    * **Garis (Edge):** Jika dua saham dihubungkan oleh garis, artinya pergerakan harian mereka memiliki korelasi positif di atas ambang batas yang Anda tentukan di menu sebelah kiri. Ketika satu naik, probabilitas yang satu lagi ikut naik sangat tinggi.
    """)
