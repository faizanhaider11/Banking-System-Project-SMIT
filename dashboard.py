import streamlit as st
import pandas as pd
from supabase import create_client, Client

SUPABASE_URL = "https://tglrviwyeindydnuugdv.supabase.co"
SUPABASE_KEY = "sb_publishable_ypfWRKRGgkqo3yaVKLdL3g_AUVWF831"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Digital Banking Core", layout="wide")
st.title("🏦 Digital Banking Backend & Ops Automation")

tab1, tab2, tab3 = st.tabs(["📊 Ledger & Accounts", "💸 Transfer Funds", "⚙️ Ops & Reconciliation"])

# TAB 1: Ledger & Accounts View
with tab1:
    st.header("Accounts Ledger (Supabase)")
    if st.button("Refresh Ledger"):
        acc_res = supabase.table("accounts").select("*").execute()
        holders_res = supabase.table("account_holders").select("*").execute()
        
        st.subheader("Accounts Table")
        st.dataframe(pd.DataFrame(acc_res.data), use_container_width=True)
        
        st.subheader("Account Holders Table")
        st.dataframe(pd.DataFrame(holders_res.data), use_container_width=True)

# TAB 2: Direct Supabase RPC Transfer
with tab2:
    st.header("Atomic Transfer (ACID Protected)")
    col1, col2 = st.columns(2)
    with col1:
        sender_id = st.text_input("Sender Account UUID", value="11111111-1111-1111-1111-111111111111")
        receiver_id = st.text_input("Receiver Account UUID", value="22222222-2222-2222-2222-222222222222")
    with col2:
        amount = st.number_input("Amount", min_value=1.0, value=100.0)
        idempotency_key = st.text_input("Idempotency Key (Unique)", value="TXN_1001")
        
    if st.button("Execute Transfer"):
        try:
            res = supabase.rpc("process_transfer", {
                "p_idempotency_key": str(idempotency_key),
                "p_sender_id": str(sender_id),
                "p_receiver_id": str(receiver_id),
                "p_amount": float(amount)
            }).execute()
            
            st.success(f"Transfer Response: {res.data}")
        except Exception as e:
            st.error(f"Transfer Error: {str(e)}")

# TAB 3: Ops & Reconciliation
with tab3:
    st.header("Automated Operations")
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("Nightly Reconciliation (Pandas)")
        if st.button("Run Ledger Reconciliation Job"):
            tx_res = supabase.table("transactions").select("*").execute()
            st.write("Transactions Audit Log:")
            st.dataframe(pd.DataFrame(tx_res.data), use_container_width=True)
            
    with col_b:
        st.subheader("Minor to Adult Conversion")
        if st.button("Run Age 18+ Status Upgrade Trigger"):
            holders_res = supabase.table("account_holders").select("account_id, age, role").eq("role", "minor").gte("age", 18).execute()
            converted = []
            for holder in holders_res.data:
                acc_id = holder["account_id"]
                supabase.table("account_holders").update({"role": "primary"}).eq("account_id", acc_id).execute()
                supabase.table("accounts").update({"account_type": "single"}).eq("id", acc_id).execute()
                converted.append(acc_id)
            st.success(f"Converted Accounts: {len(converted)}")