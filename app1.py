import streamlit as st

# 1. 認証設定
if "pocket" in st.secrets:
    POCKET_API_KEY = st.secrets["pocket"].get("api_key", "XZtsg3OrDFOh0VayOI83j84Oc3YIzm7oujbI0T08")
    st.sidebar.success("✅ st.secrets からキーを読み込みました")
else:
    POCKET_API_KEY = "XZtsg3OrDFOh0VayOI83j84Oc3YIzm7oujbI0T08"
    st.sidebar.warning("⚠️ secrets.toml が見つからないためフォールバック値を使用中")

correct_last4 = POCKET_API_KEY[-4:]

# 【デバッグ用】現在システムが認識している「正解の下4桁」を画面に表示して確認する
# （※確認ができたらこの行は削除して大丈夫です）
st.info(f"💡 [デバッグ表示] 現在設定されているキーの末尾4桁は **{correct_last4}** です")

# 2. UI入力
user_input_last4 = st.text_input("🔑 セキュリティ確認：APIキーの下4桁を入力してください", type="password", max_chars=4)

if not user_input_last4:
    st.warning("⚠️ 利用するにはAPIキーの下4桁を入力してください。")
    st.stop()

if user_input_last4 != correct_last4:
    st.error("❌ APIキーの下4桁が一致しません。")
    st.stop()

st.success("✨ 認証成功しました！")