import os
import requests
import streamlit as st

st.set_page_config(page_title="外発注データ・デバッグ確認ツール", layout="centered")
st.title("🔍 外発注明細テーブル・フィールドIDデバッグ")

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

# セキュリティ：APIキーの下4桁認証
correct_last4 = POCKET_API_KEY[-4:]
user_input_last4 = st.text_input("🔑 セキュリティ確認：APIキーの下4桁を入力してください", type="password", max_chars=4)

if not user_input_last4:
    st.warning("⚠️ 利用するにはAPIキーの下4桁を入力してください。")
    st.stop()

if user_input_last4 != correct_last4:
    st.error("❌ APIキーの下4桁が一致しません。")
    st.stop()

st.success("✨ 認証成功しました！")

# ==========================================
# 受注番号入力
# ==========================================
input_order_no = st.text_input("デバッグしたい受注番号（field-95）を入力してください")

if input_order_no:
    url = f"{POCKET_BASE_URL}/api/apps/{APP_ID}/records"
    headers = {"X-At-Pocket-API-Key": POCKET_API_KEY, "Accept": "application/json"}
    # メインテーブルの受注番号フィールド (field-95) でクエリ
    params = {"query": f'field-95 = "{input_order_no}"'}
    
    with st.spinner("APIからデータを取得中..."):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            if response.status_code == 200:
                result = response.json()
                records = result.get("records", result.get("Data", result.get("Records", [])))
                
                if records:
                    st.success(f"✅ レコードが見つえました！（件数: {len(records)}件）")
                    
                    # 最初に見つかったレコードを解析
                    item = records[0]
                    rec_body = item.get("record", {})
                    
                    # メイン情報の表示
                    st.subheader("📌 メインテーブル情報")
                    st.write(f"- **受注番号 (field-95)**: {rec_body.get('field-95', '')}")
                    st.write(f"- **営業担当者 (field-100)**: {rec_body.get('field-100', '')}")
                    st.write(f"- **得意先名 (field-98)**: {rec_body.get('field-98', '')}")
                    
                    # 各明細テーブル（サブテーブル）のデバッグ表示
                    st.subheader("📦 各明細テーブルの生データ（JSON確認用）")
                    
                    sub_fields = {
                        "用紙外発注 (field-151)": "field-151",
                        "印刷外発注 (field-162)": "field-162",
                        "製本外発注 (field-153)": "field-153",
                        "その他外発注 (field-155)": "field-155"
                    }
                    
                    for label, field_id in sub_fields.items():
                        sub_data = rec_body.get(field_id, [])
                        with st.expander(f"{label} （データ数: {len(sub_data) if isinstance(sub_data, list) else 'なし'}）"):
                            st.json(sub_data)
                            
                    # レコード全体の構造も確認できるようにする
                    with st.expander("🔍 レコード全体の生JSON構造を見る"):
                        st.json(item)
                        
                else:
                    st.error(f"❌ 受注番号「{input_order_no}」に一致するレコードが見つかりませんでした。")
            else:
                st.error(f"❌ APIエラー (ステータスコード: {response.status_code})")
        except Exception as e:
            st.error(f"通信エラーが発生しました: {e}")