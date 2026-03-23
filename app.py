import streamlit as st
import plotly.graph_objects as go
import os
import pandas as pd
import io
import base64
import sqlite3
import requests
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch

# -------------------- PAGE CONFIG --------------------
st.set_page_config(page_title="Industrial IoT Surveillance", layout="wide")

# -------------------- DATABASE --------------------
conn = sqlite3.connect("iot_data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS sensor_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    temperature REAL,
    humidity REAL,
    gas REAL,
    status TEXT
)
""")
conn.commit()

# -------------------- LOGIN --------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

USERNAME = "admin"
PASSWORD = "1234"

def login():
    st.title("🔐 Industrial Login Portal")
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if user == USERNAME and pwd == PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Invalid Credentials ❌")

if not st.session_state.logged_in:
    login()
    st.stop()

if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.rerun()

# -------------------- AUTO REFRESH --------------------
st_autorefresh(interval=2000, key="refresh")

# -------------------- HEADER --------------------
st.title("🏭 INDUSTRIAL IoT MONITORING SYSTEM")

now = datetime.now()
st.write(f"📅 {now.strftime('%d-%m-%Y')} | ⏰ {now.strftime('%H:%M:%S')}")

# -------------------- THRESHOLDS --------------------
GAS_THRESHOLD = 100
TEMP_THRESHOLD = 32

# -------------------- ESP DATA --------------------
ESP8266_IP = "http://10.127.247.54"

try:
    response = requests.get(ESP8266_IP, timeout=2)
    data = response.json()

    temperature = float(data["temperature"])
    humidity = float(data["humidity"])
    gas = float(data["gas"])

except:
    st.error("⚠ ESP8266 Not Connected")
    temperature = 0
    humidity = 0
    gas = 0

# -------------------- STATUS --------------------
status = "SAFE"
if gas > GAS_THRESHOLD or temperature > TEMP_THRESHOLD:
    status = "DANGER"

if status == "SAFE":
    st.success("✅ SYSTEM STATUS : SAFE")
else:
    st.error("🚨 SYSTEM STATUS : DANGER")

# -------------------- BUZZER --------------------
if status == "DANGER" and os.path.exists("buzzer.mp3"):
    with open("buzzer.mp3", "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()

    st.markdown(f"""
    <audio autoplay loop>
        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
    </audio>
    """, unsafe_allow_html=True)

# -------------------- STORE DATA --------------------
cursor.execute("""
INSERT INTO sensor_data (timestamp, temperature, humidity, gas, status)
VALUES (?, ?, ?, ?, ?)
""", (
    now.strftime("%Y-%m-%d %H:%M:%S"),  # full format in DB
    temperature,
    humidity,
    gas,
    status
))
conn.commit()

# -------------------- GAUGES --------------------
col1, col2, col3 = st.columns(3)

with col1:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=temperature,
        title={'text': "Temperature (°C)"},
        gauge={'axis': {'range': [0, 50]}}
    ))
    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=humidity,
        title={'text': "Humidity (%)"},
        gauge={'axis': {'range': [0, 100]}}
    ))
    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

with col3:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=gas,
        title={'text': "Gas Level (ppm)"},
        gauge={'axis': {'range': [0, 1000]}}
    ))
    fig.update_layout(template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

# -------------------- RECENT LOGS --------------------
df = pd.read_sql_query(
    "SELECT * FROM sensor_data ORDER BY id DESC LIMIT 10",
    conn
)

# ✅ FIX TIMESTAMP DISPLAY
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["timestamp"] = df["timestamp"].dt.strftime("%d-%m %H:%M")

# Rename columns for clean UI
df.rename(columns={
    "timestamp": "Time",
    "temperature": "Temp (°C)",
    "humidity": "Humidity (%)",
    "gas": "Gas (ppm)",
    "status": "Status"
}, inplace=True)

st.subheader("📊 Recent Logs")
st.dataframe(df, use_container_width=True)

# -------------------- TREND GRAPH --------------------
full_df = pd.read_sql_query(
    "SELECT * FROM sensor_data ORDER BY id ASC",
    conn
)

if len(full_df) > 1:
    full_df["timestamp"] = pd.to_datetime(full_df["timestamp"])

    for col_name, title in [
        ("temperature", "Temperature (°C)"),
        ("humidity", "Humidity (%)"),
        ("gas", "Gas Level (ppm)")
    ]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=full_df["timestamp"],
            y=full_df[col_name],
            mode="lines+markers"
        ))
        fig.update_layout(
            template="plotly_dark",
            title=f"{title} Trend",
            xaxis_title="Time",
            yaxis_title=title
        )
        st.plotly_chart(fig, use_container_width=True)

# -------------------- DOWNLOAD CSV --------------------
csv = full_df.to_csv(index=False).encode('utf-8')

st.download_button(
    "📥 Download Full Data (CSV)",
    data=csv,
    file_name="iot_data.csv",
    mime="text/csv"
)

# -------------------- CLEAR DATABASE --------------------
if st.button("🗑 Clear Database"):
    cursor.execute("DELETE FROM sensor_data")
    conn.commit()
    st.success("Database Cleared!")

# -------------------- PDF REPORT --------------------
def generate_pdf():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    if os.path.exists("logo.png"):
        logo = Image("logo.png")
        logo.drawWidth = 6 * inch
        logo.drawHeight = 2.5 * inch
        elements.append(logo)
        elements.append(Spacer(1, 20))

    elements.append(Paragraph("<b>Industrial IoT Monitoring Report</b>", styles["Title"]))
    elements.append(Spacer(1, 20))

    data = [
        ["Parameter", "Value"],
        ["Temperature", f"{temperature:.2f}"],
        ["Humidity", f"{humidity:.2f}"],
        ["Gas", f"{gas:.2f}"],
        ["Status", status]
    ]

    elements.append(Table(data))
    doc.build(elements)

    buffer.seek(0)
    return buffer

st.download_button(
    "📄 Download PDF Report",
    data=generate_pdf(),
    file_name="report.pdf",
    mime="application/pdf"
)