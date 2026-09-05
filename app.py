import streamlit as st

st.title("⚽ Premier League Scout")

st.write("Find players that match your club's recruitment needs.")

position = st.selectbox(
    "Select a position",
    [
        "Goalkeeper",
        "Defender",
        "Midfielder",
        "Forward"
    ]
)

st.write("You selected:", position)