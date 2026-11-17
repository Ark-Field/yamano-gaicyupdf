import os
import io
import requests
import pandas as pd
import streamlit as st
from datetime import date, datetime
from reportlab.lib.pagesizes import landscape, A5
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ==========================================
# ページ基本設定
# ==========================================
st.set_page_config(page_title="外発注管理・発注書＆期間集計ツール", layout="wide")
st.title("📦 外発注管理・発注書作成 & 分割期間集計ツール")

# ==========================================
# 🔐 パスワード認証チェック（ログイン画面）
# ==========================================
# セッション状態の初期化
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.subheader("🔒 ログイン認証が必要です")
    
    # Secretsからパスワードを取得（未設定の場合はデフォルト値）
    correct_password = st.secrets.get("APP_PASSWORD", "admin1234")
    
    entered_password = st.text_input("パスワードを入力してください", type="password")
    
    if st.button("ログイン", type="primary"):
        if entered_password == correct_password:
            st.session_state.authenticated = True
            st.success("✨ ログインに成功しました！")
            st.rerun()
        else:
            st.error("❌ パスワードが間違っています。")
    
    # 認証されていない場合はここで処理をストップ（メイン画面を表示しない）
    st.stop()

# ==========================================
# 以降は認証成功後に表示されるメイン処理
# ==========================================

# @pocket認証設定 (Streamlit Secretsから読み込み)
try:
    POCKET_API_KEY = st.secrets["POCKET_API_KEY"]
    st.sidebar.success("🔑 APIキー設定完了 (Secretsから読込)")
except Exception:
    POCKET_API_KEY = ""
    st.sidebar.error("⚠️ Secretsに `POCKET_API_KEY` が設定されていません。")

POCKET_BASE_URL = "https://app050.at-pocket.com/seihon01_bb"
APP_ID = 41  # 発注アプリのApp ID

# （以下、既存のタブや関数などのコードが続きます...）