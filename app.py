import streamlit as st
import yfinance as yf
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Konfigurasi Halaman Streamlit
st.set_page_config(page_title="Analisis Jaringan Saham IDX", layout="wide")
st.title("🕸️ Analisis Jaringan Korelasi Saham Indonesia (IDX) - Versi 2")
st.markdown("""
Dashboard ini memvisualisasikan saham-saham yang bergerak searah. 
Garis yang menghubungkan dua saham menunjukkan korelasi positif yang kuat di antara keduanya.
""")

# --- SIDEBAR PENGATURAN ---
st.sidebar.header("Pengaturan Analisis")

# Daftar Saham Default (Bluechips & Tech)
default_tickers = "BBCA.JK, BBRI.JK, BMRI.JK, BBNI.JK, TLKM.JK, ASII.JK, GOTO.JK, AMMN.JK, BREN.JK, UNVR.JK, ICBP.JK, PGAS.JK, ADRO.JK, PTBA.JK"
tickers_input = st.sidebar.text_area("Masukkan Kod Saham (Gunakan .JK untuk saham Indonesia):", default_tickers)
# Membersihkan senarai ticker
tickers_list = [ticker.strip() for ticker in tickers_input.split(',') if ticker.strip()]

# Pengaturan Waktu
end_date = datetime.today()
start_date = end_date - timedelta(days=365) # Default 1 tahun terakhir
start = st.sidebar.date_input("Tarikh Mula", start_date)
end = st.sidebar.date_input("Tarikh Akhir", end_date)

# Batas Korelasi
corr_threshold = st.sidebar.slider("Batas Korelasi Minimum", min_value=0.0, max_value=1.0, value=0.6, step=0.05, 
                                   help="Semakin tinggi nilainya, semakin ketat hubungannya. 0.6 bermakna korelasi positif yang agak kuat.")

# --- MENGAMBIL DATA (DIPERBAIKI) ---
@st.cache_data
def load_data(tickers, start, end):
    try:
        if not tickers:
            return "Sila masukkan sekurang-kurangnya satu kod saham."

        # Memuat turun data
        df = yf.download(tickers, start=start, end=end, progress=False)
        
        # Semak jika data kosong
        if df.empty:
            return "Data tidak ditemui untuk julat tarikh ini."

        # Tangani struktur multi-index yfinance dan cari 'Adj Close' atau 'Close'
        if 'Adj Close' in df.columns:
            data = df['Adj Close']
        elif 'Close' in df.columns:
            data = df['Close']
        else:
             return "Lajur 'Adj Close' atau 'Close' tidak wujud dalam data yang dimuat turun."

        # Jika hanya 1 saham, yfinance mengembalikan Series, kita perlu tukar ke DataFrame
        if isinstance(data, pd.Series):
            data = data.to_frame(name=tickers[0])

        # Buang lajur (saham) yang tidak mempunyai sebarang data (Semua NaN)
        data = data.dropna(axis=1, how='all')
        
        if data.empty or data.shape[1] < 2:
            return "Data tidak mencukupi untuk mengira korelasi. Pastikan sekurang-kurangnya 2 saham mempunyai data yang sah."

        # Mengira peratusan perubahan harian (return)
        returns = data.pct_change().dropna(how='all')
        
        # Mengira matriks korelasi
        corr_matrix = returns.corr()
        return corr_matrix

    except Exception as e:
        return f"Ralat sistem: {str(e)}"

with st.spinner("Memuat turun data dan mengira korelasi..."):
    corr_matrix = load_data(tickers_list, start, end)

# --- PAPARAN HASIL / RALAT ---
if isinstance(corr_matrix, str):
    # Jika ia memulangkan rentetan (string), bermaksud ada ralat
    st.error(f"Terjadi kesalahan saat mengambil data: {corr_matrix}")
else:
    # --- MEMBUAT JARINGAN (NETWORK) ---
    G = nx.Graph()
    
    # Dapatkan senarai saham yang berjaya dimuat turun (berdasarkan lajur matriks)
    valid_tickers = corr_matrix.columns.tolist()

    # Menambah Node (Saham)
    for ticker in valid_tickers:
        G.add_node(ticker)

    # Menambah Edge (Garis Koneksi) berdasarkan Threshold Korelasi
    for i in range(len(valid_tickers)):
        for j in range(i+1, len(valid_tickers)):
            stock1 = valid_tickers[i]
            stock2 = valid_tickers[j]
            korelasi = corr_matrix.iloc[i, j]
            
            # Semak jika nilai korelasi sah (bukan NaN) dan melepasi batas
            if pd.notna(korelasi) and korelasi >= corr_threshold:
                G.add_edge(stock1, stock2, weight=korelasi)

    # --- VISUALISASI DENGAN PLOTLY ---
    if G.number_of_nodes() == 0:
        st.warning("Tiada data yang mencukupi untuk dipaparkan.")
    else:
        # Mengatur susun atur node (spring layout)
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
        node_color = []
        
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            
            # Kira jumlah sambungan
            connections = len(list(G.neighbors(node)))
            node_color.append(connections)
            node_text.append(f"<b>{node.replace('.JK', '')}</b><br>Koneksi: {connections}")

        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            text=[node.replace('.JK', '') for node in G.nodes()], 
            textposition="bottom center",
            hoverinfo='text',
            hovertext=node_text,
            marker=dict(
                showscale=True,
                colorscale='YlGnBu',
                reversescale=True,
                color=node_color,
                size=35,
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
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                     ))

        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("""
        **Cara Membaca:**
        * **Titik (Node):** Mewakili satu saham. Semakin gelap/berbeza warnanya, semakin banyak saham lain yang berkorelasi dengannya.
        * **Garis (Edge):** Jika dua saham dihubungkan oleh garis, ertinya pergerakan harian mereka memiliki korelasi positif di atas ambang batas. Apabila satu naik, probabiliti yang satu lagi ikut naik adalah sangat tinggi.
        """)
