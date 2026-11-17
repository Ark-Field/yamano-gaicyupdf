import os
import io
import requests
import pandas as pd
import streamlit as st

# ==========================================
# ページ基本設定
# ==========================================
st.set_page_config(page_title="外発注管理・発注書＆期間集計ツール（テスト版）", layout="wide")
st.title("📦 外発注管理・発注書作成 & 期間集計ツール（ベタ打ちテスト）")

# ==========================================
# @pocket認証設定 (一時的なベタ打ち)
# ==========================================
POCKET_API_KEY = "AfMdA3MjacXouAAhgaWFfchlwcIsCKf2ToIOl9OW"
POCKET_BASE_URL = "https://app050.at-pocket.com/seihon01_bb"
APP_ID = 41  # 発注アプリのApp ID

st.sidebar.success("🔑 APIキーを直接読み込んでテスト中")

# ==========================================
# データ取得関数
# ==========================================
@st.cache_data(ttl=60)
def fetch_all_records():
    url = f"{POCKET_BASE_URL}/api/apps/{APP_ID}/records"
    headers = {"X-At-Pocket-API-Key": POCKET_API_KEY, "Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        st.write(f"🔍 [debug] 全件取得APIステータスコード: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            return result.get("records", result.get("Data", result.get("Records", [])))
        else:
            st.error(f"APIエラー: {response.text}")
    except Exception as e:
        st.error(f"API通信エラー: {e}")
    return []

def fetch_record_by_order(order_no):
    url = f"{POCKET_BASE_URL}/api/apps/{APP_ID}/records"
    headers = {"X-At-Pocket-API-Key": POCKET_API_KEY, "Accept": "application/json"}
    params = {"query": f'field-95 = "{order_no}"'}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        st.write(f"🔍 [debug] 受注番号検索APIステータスコード: {response.status_code}")
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
    
    input_order_no = st.text_input("受注番号（field-95）を入力してください", placeholder="例: 受注番号を入力")
    
    if input_order_no:
        with st.spinner(f"受注番号 {input_order_no} のデータを取得中..."):
            record_data = fetch_record_by_order(input_order_no)
            
        if record_data:
            rec = record_data.get("record", record_data)
            st.success("✨ レコードの取得に成功しました！")
            
            # メイン情報の表示
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("受注番号", rec.get('field-95', ''))
            with col2:
                st.metric("得意先名", rec.get('field-98', ''))
            with col3:
                st.metric("営業担当者", rec.get('field-100', ''))
                
            st.markdown("---")
            st.markdown("### 📦 外発注明細テーブル一覧")
            
            sub_tables = {
                "用紙外発注 (field-151)": "field-151",
                "印刷外発注 (field-162)": "field-162",
                "製本外発注 (field-153)": "field-153",
                "その他外発注 (field-155)": "field-155"
            }
            
            selected_