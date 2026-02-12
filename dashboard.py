import sqlite3
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Vols Japon", layout="wide")

st.title("✈️ Surveillance des vols Nice → Japon")

conn = sqlite3.connect("flights.db")

df = pd.read_sql_query(
    "SELECT * FROM flights ORDER BY checked_at DESC",
    conn
)

if df.empty:
    st.info("Aucun vol enregistré pour le moment.")
else:
    st.metric("Nombre de vols trouvés", len(df))

    st.dataframe(df)

    st.subheader("Évolution des prix")

    df["checked_at"] = pd.to_datetime(df["checked_at"])
    df = df.sort_values("checked_at")

    st.line_chart(df[["checked_at", "price"]].set_index("checked_at"))
