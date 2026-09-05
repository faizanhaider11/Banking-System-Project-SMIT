import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
import pandas as pd
import numpy as np

# Supabase Credentials
SUPABASE_URL = "https://tglrviwyeindydnuugdv.supabase.co"
SUPABASE_KEY = "sb_publishable_ypfWRKRGgkqo3yaVKLdL3g_AUVWF831"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = FastAPI(title="Digital Banking Backend Engine")

# --- Models ---
class TransferRequest(BaseModel):
    idempotency_key: str
    sender_account_id: str
    receiver_account_id: str
    amount: float

# --- 1. Atomic Transfer Logic (RPC Call) ---
@app.post("/transfer")
def execute_transfer(req: TransferRequest):
    try:
        response = supabase.rpc("process_transfer", {
            "p_idempotency_key": str(req.idempotency_key),
            "p_sender_id": str(req.sender_account_id),
            "p_receiver_id": str(req.receiver_account_id),
            "p_amount": float(req.amount)
        }).execute()
        
        result = response.data
        if isinstance(result, dict) and result.get("status") in ["failed", "rejected"]:
            raise HTTPException(status_code=400, detail=str(result.get("message")))
            
        return {"status": "success", "data": result}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. Nightly Reconciliation Job (Pandas) ---
@app.get("/reconcile")
def run_nightly_reconciliation():
    accounts_res = supabase.table("accounts").select("id, balance").execute()
    tx_res = supabase.table("transactions").select("sender_account_id, receiver_account_id, amount, status").execute()
    
    accounts_df = pd.DataFrame(accounts_res.data)
    tx_df = pd.DataFrame(tx_res.data)
    
    if tx_df.empty:
        return {"status": "reconciled", "discrepancies": 0}
        
    completed_tx = tx_df[tx_df['status'] == 'completed']
    
    debits = completed_tx.groupby('sender_account_id')['amount'].sum().reset_index()
    debits.columns = ['id', 'total_debits']
    
    credits = completed_tx.groupby('receiver_account_id')['amount'].sum().reset_index()
    credits.columns = ['id', 'total_credits']
    
    merged = pd.merge(accounts_df, debits, on='id', how='left').fillna(0)
    merged = pd.merge(merged, credits, on='id', how='left').fillna(0)
    
    merged['expected_balance'] = merged['total_credits'] - merged['total_debits']
    merged['discrepancy'] = merged['balance'] - merged['expected_balance']
    
    discrepancies = merged[merged['discrepancy'] != 0]
    
    return {
        "status": "reconciled",
        "total_accounts_checked": len(merged),
        "discrepancies_found": len(discrepancies),
        "details": discrepancies.to_dict(orient="records")
    }

# --- 3. Minor Account Conversion Trigger ---
@app.post("/convert-minors")
def check_and_convert_minor_accounts():
    holders_res = supabase.table("account_holders").select("account_id, age, role").eq("role", "minor").gte("age", 18).execute()
    converted = []
    
    for holder in holders_res.data:
        acc_id = holder["account_id"]
        supabase.table("account_holders").update({"role": "primary"}).eq("account_id", acc_id).execute()
        supabase.table("accounts").update({"account_type": "single"}).eq("id", acc_id).execute()
        converted.append(acc_id)
        
    return {"status": "success", "converted_accounts_count": len(converted), "converted_ids": converted}