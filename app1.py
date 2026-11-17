import os
import io
import requests
import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import landscape, A5
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ==========================================
# ページ基本設定
# ==========================================
st.set_page_config(page_title="外発注管理・発注書＆期間集計ツール", layout="wide")
st.title("📦 外発注管理・発注書作成 & 期間集計ツール")

# ==========================================
# @pocket認証設定 (ベタ打ちテスト版)
# ==========================================
POCKET_API_KEY = "AfMdA3MjacXouAAhgaWFfchlwcIsCKf2ToIOl9OW"
POCKET_BASE_URL = "https://app050.at-pocket.com/seihon01_bb"
APP_ID = 41  # 発注アプリのApp ID

st.sidebar.success("🔑 APIキー設定完了 (App ID: 41)")

# ==========================================
# 項目名（日本語ラベル）のマッピング辞書
# ==========================================
LABEL_MAPPINGS = {
    "field-151": {
        "field-151_1": "用途", "field-151_22": "納品先", "field-151_2": "用紙銘柄",
        "field-151_25": "原紙サイズ", "field-151_4": "斤量", "field-151_3": "目",
        "field-151_20": "全判紙数", "field-151_26": "断裁後サイズ", "field-151_35": "納入枚数",
        "field-151_17": "納入日", "field-151_23": "時間", "field-151_24": "備考",
        "field-151_18": "発注先", "field-151_16": "発注者",
    },
    "field-162": {
        "field-162_19": "用途", "field-162_17": "納品先", "field-162_1": "用紙銘柄",
        "field-162_2": "印刷サイズ", "field-162_21": "斤量", "field-162_20": "目",
        "field-162_6": "通数", "field-162_7": "頁数", "field-162_9": "色表",
        "field-162_10": "色裏", "field-162_11": "台数", "field-162_12": "版数",
        "field-162_13": "納入日", "field-162_18": "時間", "field-162_16": "備考",
        "field-162_5": "発注先", "field-162_14": "発注者",
    },
    "field-153": {
        "field-153_1": "用途", "field-153_31": "納品先", "field-153_33": "製本",
        "field-153_34": "加工", "field-153_29": "詳細", "field-153_8": "部数",
        "field-153_26": "納入日", "field-153_32": "時間", "field-153_12": "備考",
        "field-153_27": "発注先", "field-153_9": "発注者"
    },
    "field-155": {
        "field-155_6": "発注先", "field-155_10": "納品先", "field-155_7": "数量",
        "field-155_3": "仕入単価", "field-155_9": "合計金額", "field-155_4": "納入日",
        "field-155_8": "時間", "field-155_1": "作業内容・仕様", "field-155_11": "備考",
        "field-155_5": "発注者",
    }
}

def parse_sub_table(sub_list, target_field_id):
    flattened = []
    mapping = LABEL_MAPPINGS.get(target_field_id, {})
    if isinstance(sub_list, list):
        for item in sub_list:
            if isinstance(item, dict):
                sub_id = item.get("recordSubId", "")
                rec_inner = item.get("record", {})
                row_data = {"明細ID": sub_id}
                if isinstance(rec_inner, dict):
                    for k, v in rec_inner.items():
                        jp_label = mapping.get(k, k)
                        row_data[jp_label] = v
                flattened.append(row_data)
    return flattened

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
# PDF生成関数 (A5横サイズ)
# ==========================================
def generate_order_pdf(rec, sub_type, supplier_name, rows_data):
    buffer = io.BytesIO()
    # A5横サイズ (Landscape A5: width=595.27, height=419.52 points)
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A5), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
    
    # フォント登録
    font_path = "NotoSansJP-Regular.ttf"
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('NotoSansJP', font_path))
        font_name = 'NotoSansJP'
    else:
        font_name = 'Helvetica'
        
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', fontName=font_name, fontSize=14, leading=16, alignment=1)
    cell_style = ParagraphStyle('CellStyle', fontName=font_name, fontSize=8, leading=10)
    header_cell_style = ParagraphStyle('HeaderCellStyle', fontName=font_name, fontSize=8, leading=10, textColor=colors.HexColor('#333333'))
    
    story = []
    
    # タイトル & ヘッダー情報
    order_no = rec.get('field-95', '')
    customer = rec.get('field-98', '')
    staff = rec.get('field-100', '')
    
    title_text = f"<b>発 注 書（{sub_type}）</b>"
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 10))
    
    header_data = [
        [Paragraph(f"<b>発注先:</b> {supplier_name} 御中", cell_style), Paragraph(f"<b>受注番号:</b> {order_no}", cell_style)],
        [Paragraph(f"<b>得意先名:</b> {customer}", cell_style), Paragraph(f"<b>営業担当:</b> {staff}", cell_style)]
    ]
    t_header = Table(header_data, colWidths=[250, 285])
    t_header.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.grey),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9F9F9')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 15))
    
    # 明細テーブルの構築（種別ごとのレイアウト）
    table_content = []
    
    if sub_type == "用紙外発注":
        # ヘッダー行
        table_content.append([
            Paragraph("<b>用途</b>", header_cell_style), Paragraph("<b>納品先</b>", header_cell_style),
            Paragraph("<b>用紙銘柄</b>", header_cell_style), Paragraph("<b>原紙サイズ</b>", header_cell_style),
            Paragraph("<b>斤量</b>", header_cell_style), Paragraph("<b>目</b>", header_cell_style),
            Paragraph("<b>全判</b>", header_cell_style), Paragraph("<b>断裁後</b>", header_cell_style),
            Paragraph("<b>枚数</b>", header_cell_style), Paragraph("<b>納入日</b>", header_cell_style),
            Paragraph("<b>時間</b>", header_cell_style)
        ])
        for row in rows_data:
            # 1レコード2行組表現（1行目：基本情報、2行目：備考など）
            n_date = str(row.get('納入日', ''))[5:] # 月日表示
            table_content.append([
                Paragraph(str(row.get('用途', '')), cell_style),
                Paragraph(str(row.get('納品先', '')), cell_style),
                Paragraph(str(row.get('用紙銘柄', '')), cell_style),
                Paragraph(str(row.get('原紙サイズ', '')), cell_style),
                Paragraph(str(row.get('斤量', '')), cell_style),
                Paragraph(str(row.get('目', '')), cell_style),
                Paragraph(str(row.get('全判紙数', '')), cell_style),
                Paragraph(str(row.get('断裁後サイズ', '')), cell_style),
                Paragraph(str(row.get('納入枚数', '')), cell_style),
                Paragraph(n_date, cell_style),
                Paragraph(str(row.get('時間', '')), cell_style)
            ])
            # 備考行（2段目）
            remark_text = f"<b>備考:</b> {row.get('備考', '')}"
            table_content.append([Paragraph(remark_text, cell_style), '', '', '', '', '', '', '', '', '', ''])
            
    elif sub_type == "印刷外発注":
        table_content.append([
            Paragraph("<b>用途</b>", header_cell_style), Paragraph("<b>納品先</b>", header_cell_style),
            Paragraph("<b>用紙銘柄</b>", header_cell_style), Paragraph("<b>印刷サイズ</b>", header_cell_style),
            Paragraph("<b>斤量</b>", header_cell_style), Paragraph("<b>目</b>", header_cell_style),
            Paragraph("<b>通数</b>", header_cell_style), Paragraph("<b>頁数</b>", header_cell_style),
            Paragraph("<b>表/裏</b>", header_cell_style), Paragraph("<b>台/版</b>", header_cell_style),
            Paragraph("<b>納入日</b>", header_cell_style)
        ])
        for row in rows_data:
            n_date = str(row.get('納入日', ''))[5:]
            table_content.append([
                Paragraph(str(row.get('用途', '')), cell_style),
                Paragraph(str(row.get('納品先', '')), cell_style),
                Paragraph(str(row.get('用紙銘柄', '')), cell_style),
                Paragraph(str(row.get('印刷サイズ', '')), cell_style),
                Paragraph(str(row.get('斤量', '')), cell_style),
                Paragraph(str(row.get('目', '')), cell_style),
                Paragraph(str(row.get('通数', '')), cell_style),
                Paragraph(str(row.get('頁数', '')), cell_style),
                Paragraph(f"{row.get('色表','')}/{row.get('色裏','')}", cell_style),
                Paragraph(f"{row.get('台数','')}/{row.get('版数','')}", cell_style),
                Paragraph(n_date, cell_style)
            ])
            remark_text = f"<b>備考:</b> {row.get('備考', '')}"
            table_content.append([Paragraph(remark_text, cell_style), '', '', '', '', '', '', '', '', '', ''])

    elif sub_type == "製本外発注":
        table_content.append([
            Paragraph("<b>用途</b>", header_cell_style), Paragraph("<b>納品先</b>", header_cell_style),
            Paragraph("<b>製本</b>", header_cell_style), Paragraph("<b>加工</b>", header_cell_style),
            Paragraph("<b>詳細</b>", header_cell_style), Paragraph("<b>部数</b>", header_cell_style),
            Paragraph("<b>納入日</b>", header_cell_style), Paragraph("<b>時間</b>", header_cell_style),
            Paragraph("", header_cell_style), Paragraph("", header_cell_style), Paragraph("", header_cell_style)
        ])
        for row in rows_data:
            n_date = str(row.get('納入日', ''))[5:]
            table_content.append([
                Paragraph(str(row.get('用途', '')), cell_style),
                Paragraph(str(row.get('納品先', '')), cell_style),
                Paragraph(str(row.get('製本', '')), cell_style),
                Paragraph(str(row.get('加工', '')), cell_style),
                Paragraph(str(row.get('詳細', '')), cell_style),
                Paragraph(str(row.get('部数', '')), cell_style),
                Paragraph(n_date, cell_style),
                Paragraph(str(row.get('時間', '')), cell_style),
                '', '', ''
            ])
            remark_text = f"<b>備考:</b> {row.get('備考', '')}"
            table_content.append([Paragraph(remark_text, cell_style), '', '', '', '', '', '', '', '', '', ''])

    elif sub_type == "その他外発注":
        table_content.append([
            Paragraph("<b>納品先</b>", header_cell_style), Paragraph("<b>数量</b>", header_cell_style),
            Paragraph("<b>仕入単価</b>", header_cell_style), Paragraph("<b>合計金額</b>", header_cell_style),
            Paragraph("<b>納入日</b>", header_cell_style), Paragraph("<b>時間</b>", header_cell_style),
            Paragraph("", header_cell_style), Paragraph("", header_cell_style), Paragraph("", header_cell_style), Paragraph("", header_cell_style), Paragraph("", header_cell_style)
        ])
        for row in rows_data:
            n_date = str(row.get('納入日', ''))[5:]
            table_content.append([
                Paragraph(str(row.get('納品先', '')), cell_style),
                Paragraph(str(row.get('数量', '')), cell_style),
                Paragraph(str(row.get('仕入単価', '')), cell_style),
                Paragraph(str(row.get('合計金額', '')), cell_style),
                Paragraph(n_date, cell_style),
                Paragraph(str(row.get('時間', '')), cell_style),
                '', '', '', '', ''
            ])
            # 2段目：依頼内容
            table_content.append([Paragraph(f"<b>依頼内容:</b> {row.get('作業内容・仕様', '')}", cell_style), '', '', '', '', '', '', '', '', '', ''])
            # 3段目：備考
            table_content.append([Paragraph(f"<b>備考:</b> {row.get('備考', '')}", cell_style), '', '', '', '', '', '', '', '', '', ''])

    # テーブル全体のスタイル設定 (535pt幅を11列に配分)
    col_widths = [48, 52, 55, 48, 42, 38, 45, 52, 45, 55, 55]
    t_main = Table(table_content, colWidths=col_widths)
    t_main.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.grey),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0,0), (10,0), colors.HexColor('#EEEEEE')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    
    story.append(t_main)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ==========================================
# タブ構成
# ==========================================
tab_order, tab_summary = st.tabs(["📋 発注書作成・確認", "📊 期間集計"])

with tab_order:
    st.subheader("📋 受注番号ごとの外発注明細確認 & 発注書PDF作成")
    
    input_order_no = st.text_input("受注番号（field-95）を入力してください", placeholder="例: 26-0719 など")
    
    if input_order_no:
        with st.spinner(f"受注番号 {input_order_no} のデータを取得中..."):
            record_data = fetch_record_by_order(input_order_no)
            
        if record_data:
            rec = record_data.get("record", record_data)
            st.success("✨ レコードの取得に成功しました！")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("受注番号", rec.get('field-95', ''))
            with col2:
                st.metric("得意先名", rec.get('field-98', ''))
            with col3:
                st.metric("営業担当者", rec.get('field-100', ''))
                
            st.markdown("---")
            st.markdown("### 📄 発注先ごとの発注書PDFダウンロード")
            
            # 各サブテーブルのデータをパースして発注先ごとにグループ化
            target_tables = {
                "用紙外発注": ("field-151", "発注先"),
                "印刷外発注": ("field-162", "発注先"),
                "製本外発注": ("field-153", "発注先"),
                "その他外発注": ("field-155", "発注先")
            }
            
            has_supplier_data = False
            for sub_name, (f_id, supplier_key) in target_tables.items():
                raw_data = rec.get(f_id, [])
                parsed = parse_sub_table(raw_data, f_id)
                
                if parsed:
                    # 発注先ごとにグループ分け
                    suppliers = {}
                    for row in parsed:
                        sup = row.get(supplier_key, "未指定発注先")
                        if not sup:
                            sup = "未指定発注先"
                        if sup not in suppliers:
                            suppliers[sup] = []
                        suppliers[sup].append(row)
                        
                    for sup_name, rows in suppliers.items():
                        has_supplier_data = True
                        st.markdown(f"**【{sub_name}】 発注先: `{sup_name}`** （明細件数: {len(rows)}件）")
                        
                        # PDF生成ボタン
                        pdf_bytes = generate_order_pdf(rec, sub_name, sup_name, rows)
                        st.download_button(
                            label=f"📥 【{sub_name}】 {sup_name} 宛 発注書PDFをダウンロード",
                            data=pdf_bytes,
                            file_name=f"発注書_{rec.get('field-95','')}_{sub_name}_{sup_name}.pdf",
                            mime="application/pdf",
                            key=f"pdf_{f_id}_{sup_name}"
                        )
            if not has_supplier_data:
                st.info("ℹ️ この受注番号には外発注明細データが登録されていません。")
                
            with st.expander("🔍 このレコードの生JSONデータ構造を確認"):
                st.json(record_data)
        else:
            st.error(f"❌ 受注番号「{input_order_no}」に一致するレコードが見つかりませんでした。")

with tab_summary:
    st.subheader("📊 外発注の期間集計・クロス集計")
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
                    for label, f_id in [("用紙", "field-151"), ("印刷", "field-162"), ("製本", "field-153"), ("その他", "field-155")]:
                        raw_details = rec.get(f_id, [])
                        parsed_details = parse_sub_table(raw_details, f_id)
                        for d in parsed_details:
                            summary_list.append({
                                "受注番号": order_no, "得意先名": customer,
                                "営業担当": staff, "発注種別": label, "明細詳細": str(d)
                            })
                if summary_list:
                    df_summary = pd.DataFrame(summary_list)
                    st.success(f"✅ 集計完了！全 {len(df_summary)} 件の外発注明細を検出しました。")
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        st.markdown("#### 👤 営業担当者別発注件数")
                        st.dataframe(df_summary['営業担当'].value_counts().reset_index(), use_container_width=True)
                    with col_s2:
                        st.markdown("#### 🏢 得意先別発注件数")
                        st.dataframe(df_summary['得意先名'].value_counts().reset_index(), use_container_width=True)
                else:
                    st.warning("⚠️ 有効な外発注明細データが見つかりませんでした。")
            else:
                st.error("❌ レコードの取得に失敗しました。")