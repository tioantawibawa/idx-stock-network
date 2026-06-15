import streamlit as st
import yfinance as yf
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- KONFIGURASI HALAMAN ---
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
# Membersihkan list ticker
tickers_list = [ticker.strip() for ticker in tickers_input.split(',') if ticker.strip()]

# Pengaturan Waktu
end_date = datetime.today()
start_date = end_date - timedelta(days=365) # Default 1 tahun terakhir
start = st.sidebar.date_input("Tanggal Mulai", start_date)
end = st.sidebar.date_input("Tanggal Akhir", end_date)

# Batas Korelasi
corr_threshold = st.sidebar.slider("Batas Korelasi Minimum", min_value=0.0, max_value=1.0, value=0.6, step=0.05, 
                                   help="Semakin tinggi nilainya, semakin ketat hubungannya. 0.6 berarti korelasi positif yang cukup kuat.")

# --- MENGAMBIL DATA (STRATEGI ITERATIF) ---
@st.cache_data
def load_data(tickers, start, end):
    try:
        if not tickers:
            return "Silakan masukkan setidaknya satu kode saham."

        data = pd.DataFrame()
        valid_tickers_found = 0

        # Mengunduh data satu per satu agar jauh lebih stabil
        for ticker in tickers:
            try:
                # Unduh per saham
                df = yf.download(ticker, start=start, end=end, progress=False)
                
                # Pastikan data tidak kosong
                if not df.empty:
                    # Ambil harga Close atau Adj Close (mengatasi inkonsistensi yfinance)
                    if 'Adj Close' in df.columns:
                        price_series = df['Adj Close']
                    elif 'Close' in df.columns:
                        price_series = df['Close']
                    else:
                        continue # Lewati jika tidak ada kolom harga

                    # Hapus nilai NaN awal/akhir untuk memastikan ada isinya
                    price_series = price_series.dropna()
                    
                    if not price_series.empty:
                        # Masukkan ke DataFrame utama
                        data[ticker] = price_series
                        valid_tickers_found += 1
            except Exception:
                pass # Abaikan saham yang gagal diunduh dan lanjut ke saham berikutnya
        
        # Validasi apakah saham yang sukses diunduh cukup
        if valid_tickers_found < 2:
            return f"Hanya berhasil mengunduh {valid_tickers_found} saham yang valid. Pastikan rentang tanggal tidak di hari libur, dan minimal 2 kode saham aktif pada periode tersebut."

        # Isi data kosong (misal karena beda hari libur) dengan nilai sebelumnya/sesudahnya
        data = data.ffill().bfill()
        
        # Menghitung persentase perubahan harian (return)
        returns = data.pct_change().dropna(how='all')
        
        # Menghitung matriks korelasi
        corr_matrix = returns.corr()
        return corr_matrix

    except Exception as e:
        return f"Terjadi kesalahan sistem: {str(e)}"

with st.spinner("Mengunduh data dan menghitung korelasi... (Mungkin memakan waktu beberapa detik)"):
    corr_matrix = load_data(tickers_list, start, end)

# --- MENAMPILKAN HASIL ---
if isinstance(corr_matrix, str):
    st.error(corr_matrix)
else:
    # --- MEMBUAT JARINGAN (NETWORK) ---
    G = nx.Graph()
    
    valid_tickers = corr_matrix.columns.tolist()

    # Menambahkan Node (Saham)
    for ticker in valid_tickers:
        G.add_node(ticker)

    # Menambahkan Edge (Garis Koneksi) berdasarkan Threshold
    for i in range(len(valid_tickers)):
        for j in range(i+1, len(valid_tickers)):
            stock1 = valid_tickers[i]
            stock2 = valid_tickers[j]
            korelasi = corr_matrix.iloc[i, j]
            
            # Memastikan korelasi valid dan memenuhi batas
            if pd.notna(korelasi) and korelasi >= corr_threshold:
                G.add_edge(stock1, stock2, weight=korelasi)

    # --- VISUALISASI DENGAN PLOTLY ---
    if G.number_of_nodes() == 0:
        st.warning("Tidak ada data yang diproses.")
    elif G.number_of_edges() == 0:
        st.info("Tidak ada saham yang memiliki korelasi di atas batas minimum yang ditentukan. Coba turunkan 'Batas Korelasi Minimum' di sebelah kiri.")
    else:
        # Layout Spring agar node yang terkoneksi berdekatan
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
                line=dict(width=2, color='DarkSlateGrey') 
            )
        )

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
        ---
        **Cara Membaca:**
        * **Titik (Node):** Mewakili satu saham. Semakin gelap/berbeda warnanya, semakin banyak saham lain yang berkorelasi dengannya.
        * **Garis (Edge):** Jika dua saham dihubungkan oleh garis, artinya pergerakan harian mereka memiliki korelasi positif di atas batas minimum.
        """)
