import os
import io
import requests
import pandas as pd
import streamlit as st

# ==========================================
# ページ基本設定
# ==========================================
st.set_page_config(page_title="外発注管理・発注書＆期間集計ツール", layout="wide")
st.title("📦 外発注管理・発注書作成 & 期間集計ツール")

# ==========================================
# @pocket認証設定 (App ID 41用)
# ==========================================
if "pocket" in st.secrets:
    POCKET_API_KEY = st.secrets["pocket"].get("api_key", "XZtsg3OrDFOh0VayOI83j84Oc3YIzm7oujbI0T08")
    POCKET_BASE_URL = st.secrets["pocket"].get("base_url", "https://app050.at-pocket.com/seihon01_bb")
else:
    POCKET_API_KEY = "XZtsg3OrDFOh0VayOI83j84Oc3YIzm7oujbI0T08"
    POCKET_BASE_URL = "https://app050.at-pocket.com/seihon01_bb"

APP_ID = 41  # 発注アプリのApp ID

# ==========================================
# セキュリティ：APIキーの下4桁認証ブロック
# ==========================================
correct_last4 = POCKET_API_KEY[-4:]

st.sidebar.header("🔒 セキュリティ認証")
user_input_last4 = st.sidebar.text_input(
    "APIキーの下4桁を入力", 
    type="password", 
    max_chars=4,
    help="シークレットに登録されているAPIキーの末尾4桁を入力してください"
)

if not user_input_last4:
    st.warning("⚠️ 左側のサイドバーからAPIキーの下4桁を入力してください。")
    st.stop()

if user_input_last4 != correct_last4:
    st.error("❌ APIキーの下4桁が一致しません。正しいコードを入力してください。")
    st.stop()

st.sidebar.success("✨ 認証成功（システム利用可能）")

# ==========================================
# データ取得関数
# ==========================================
@st.cache_data(ttl=60)
def fetch_all_records():
    url = f"{POCKET_BASE_URL}/api/apps/{APP_ID}/records"
    headers = {"X-At-Pocket-API-Key": POCKET_API_KEY, "Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            result = response.json()
            return result.get("records", result.get("Data", result.get("Records", [])))
    except Exception as e:
        st.error(f"API通信エラー: {e}")
    return []

def fetch_record_by_order(order_no):
    url = f"{POCKET_BASE_URL}/api/apps/{APP_ID}/records"
    headers = {"X-At-Pocket-API-Key": POCKET_API_KEY, "Accept": "application/json"}
    params = {"query": f'field-95 = "{order_no}"'}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            result = response.json()
            records = result.get("records", result.get("Data", result.get("Records", [])))
            for item in records:
                rec_body = item.get("record", {})
                merged = {**item, **rec_body}
                if str(merged.get("field-95", "")) == str(order_no):
                    return merged
    except Exception as e:
        st.error(f"API通信エラー: {e}")
    return None

# ==========================================
# タブ構成
# ==========================================
tab_order, tab_summary = st.tabs(["📋 発注書作成・確認", "📊 期間集計"])

# ------------------------------------------
# タブ1: 発注書作成・確認
# ------------------------------------------
with tab_order:
    st.subheader("📋 受注番号ごとの外発注明細確認 & 発注書データ")
    
    input_order_no = st.text_input("受注番号（field-95）を入力してください", placeholder="例: 2026-001 など")
    
    if input_order_no:
        with st.spinner