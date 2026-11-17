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
        with st.spinner(f"受注番号 {input_order_no} のデータを取得中..."):
            record_data = fetch_record_by_order(input_order_no)
            
        if record_data:
            rec = record_data.get("record", record_data)
            
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
            
            # 4つの明細テーブル定義
            sub_tables = {
                "用紙外発注 (field-151)": "field-151",
                "印刷外発注 (field-162)": "field-162",
                "製本外発注 (field-153)": "field-153",
                "その他外発注 (field-155)": "field-155"
            }
            
            selected_table_name = st.selectbox("確認・出力する発注種別を選択", list(sub_tables.keys()))
            target_field_id = sub_tables[selected_table_name]
            
            sub_data = rec.get(target_field_id, [])
            
            if sub_data and isinstance(sub_data, list):
                df_sub = pd.DataFrame(sub_data)
                st.dataframe(df_sub, use_container_width=True)
                
                # Excelダウンロード機能
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_sub.to_excel(writer, index=False, sheet_name='外発注明細')
                output.seek(0)
                
                st.download_button(
                    label=f"📥 選択した明細（{selected_table_name}）をExcelでダウンロード",
                    data=output,
                    file_name=f"発注書_{input_order_no}_{target_field_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
            else:
                st.info(f"ℹ️ この受注番号には「{selected_table_name}」の明細データが登録されていないか、空です。")
                
            with st.expander("🔍 このレコードの生JSONデータ構造を確認"):
                st.json(record_data)
        else:
            st.error(f"❌ 受注番号「{input_order_no}」に一致するレコードが見つかりませんでした。")

# ------------------------------------------
# タブ2: 期間集計
# ------------------------------------------
with tab_summary:
    st.subheader("📊 外発注の期間集計・クロス集計")
    st.info("💡 登録されているすべてのレコードを一括取得し、得意先名や営業担当者ごとの外発注状況を集計します。")
    
    if st.button("🔄 データを一括取得して集計を実行", type="primary"):
        with st.spinner("全レコードを取得・集計中..."):
            all_records = fetch_all_records()
            
            if all_records:
                summary_list = []
                for item in all_records:
                    rec = item.get("record", item)
                    order_no = rec.get('field-95', '')
                    customer = rec.get('field-98', '')
                    staff = rec.get('field-100', '')
                    
                    # 各明細の件数や金額などをここで抽出して集計リストにまとめることができます
                    for label, f_id in [("用紙", "field-151"), ("印刷", "field-162"), ("製本", "field-153"), ("その他", "field-155")]:
                        details = rec.get(f_id, [])
                        if isinstance(details, list):
                            for d in details:
                                summary_list.append({
                                "受注番号": order_no,
                                "得意先名": customer,
                                "営業担当": staff,
                                "発注種別": label,
                                "明細内容": str(d)
                            })
                
                if summary_list:
                    df_summary = pd.DataFrame(summary_list)
                    st.success(f"✅ 集計完了！全 {len(df_summary)} 件の外発注明細を検出しました。")
                    
                    # 担当者別・得意先別の件数集計
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        st.markdown("#### 👤 営業担当者別発注件数")
                        staff_counts = df_summary['営業担当'].value_counts().reset_index()
                        staff_counts.columns = ['営業担当', '件数']
                        st.dataframe(staff_counts, use_container_width=True)
                        
                    with col_s2:
                        st.markdown("#### 企業 得意先別発注件数")
                        cust_counts = df_summary['得意先名'].value_counts().reset_index()
                        cust_counts.columns = ['得意先名', '件数']
                        st.dataframe(cust_counts, use_container_width=True)
                        
                    st.markdown("#### 📋 検出された全明細データ一覧")
                    st.dataframe(df_summary, use_container_width=True)
                else:
                    st.warning("⚠️ 有効な外発注明細データが見つかりませんでした。")
            else:
                st.error("❌ レコードの取得に失敗しました。")