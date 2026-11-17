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

def fetch_records_with_query(start_d=None, end_d=None, limit_count=500):
    """
    タイムアウトと1000件の壁を防ぐため、指定期間のクエリをかけて新しい順（降順）で取得する
    """
    url = f"{POCKET_BASE_URL}/api/apps/{APP_ID}/records"
    headers = {"X-At-Pocket-API-Key": POCKET_API_KEY, "Accept": "application/json"}
    
    # クエリ条件の構築（@pocketのAPI仕様に合わせた条件指定）
    query_parts = []
    if start_d:
        query_parts.append(f'updatedAt >= "{start_d} 00:00:00"')
    if end_d:
        query_parts.append(f'updatedAt <= "{end_d} 23:59:59"')
        
    params = {
        "sort": "-recordId",
        "limit": limit_count
    }
    if query_parts:
        params["query"] = " and ".join(query_parts)

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result.get("records", result.get("Data", result.get("Records", [])))
        else:
            # クエリ未対応またはエラー時のフォールバック（全件から新着順で安全に取得）
            params_fallback = {"sort": "-recordId", "limit": limit_count}
            response_fb = requests.get(url, headers=headers, params=params_fallback, timeout=30)
            if response_fb.status_code == 200:
                res_data = response_fb.json()
                return res_data.get("records", res_data.get("Data", res_data.get("Records", [])))
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
                rec_body = item.get("record", item)
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
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A5), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
    
    font_path = "NotoSansJP-Regular.ttf"
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('NotoSansJP', font_path))
        font_name = 'NotoSansJP'
    else:
        font_name = 'Helvetica'
        
    NAVY_MAIN = colors.HexColor('#1B365D')
    NAVY_LIGHT = colors.HexColor('#F0F4F8')
    TEXT_DARK = colors.HexColor('#222222')
    
    title_style = ParagraphStyle('TitleStyle', fontName=font_name, fontSize=12, leading=14, textColor=NAVY_MAIN, alignment=1)
    cell_style = ParagraphStyle('CellStyle', fontName=font_name, fontSize=7.5, leading=9.5, textColor=TEXT_DARK)
    header_cell_style = ParagraphStyle('HeaderCellStyle', fontName=font_name, fontSize=7.5, leading=9.5, textColor=colors.white)
    issuer_style = ParagraphStyle('IssuerStyle', fontName=font_name, fontSize=7.5, leading=10, textColor=TEXT_DARK)
    
    story = []
    
    order_no = rec.get('field-95', '')
    customer = rec.get('field-98', '')
    staff_name = rows_data[0].get('発注者', rec.get('field-100', '')) if rows_data else rec.get('field-100', '')
    
    issuer_html = (
        "<b>ヤマノ印刷株式会社</b><br/>"
        "〒101-0044 千代田区鍛冶町1-6-15 TEL: 03-3253-8851<br/>"
        f"<b>担当:</b> {staff_name}"
    )
    
    dest_html = (
        f"<b>発注先:</b> <font size=10><b>{supplier_name} 御中</b></font><br/>"
        f"<b>受注番号:</b> {order_no}  <b>得意先名:</b> {customer}"
    )
    
    header_table_data = [
        [Paragraph(f"<b>発 注 書（{sub_type}）</b>", title_style), Paragraph("", issuer_style)],
        [Paragraph(issuer_html, issuer_style), Paragraph(dest_html, issuer_style)]
    ]
    
    t_header = Table(header_table_data, colWidths=[215, 340])
    t_header.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('BACKGROUND', (0,0), (-1,-1), NAVY_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, NAVY_MAIN),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D0DCE5')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 10))
    
    table_content = []
    table_styles = [
        ('BOX', (0,0), (-1,-1), 1, NAVY_MAIN),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0,0), (-1,0), NAVY_MAIN),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]
    
    col_widths = [48, 52, 55, 48, 42, 38, 45, 52, 45, 55, 55]
    
    if sub_type == "用紙外発注":
        table_content.append([
            Paragraph("用途", header_cell_style), Paragraph("納品先", header_cell_style),
            Paragraph("用紙銘柄", header_cell_style), Paragraph("原紙サイズ", header_cell_style),
            Paragraph("斤量", header_cell_style), Paragraph("目", header_cell_style),
            Paragraph("全判", header_cell_style), Paragraph("断裁後", header_cell_style),
            Paragraph("枚数", header_cell_style), Paragraph("納入日", header_cell_style),
            Paragraph("時間", header_cell_style)
        ])
        for row in rows_data:
            n_date = str(row.get('納入日', ''))[5:]
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
            r_idx = len(table_content)
            table_content.append([Paragraph(f"<b>備考:</b> {row.get('備考', '')}", cell_style)] + [''] * 10)
            table_styles.append(('SPAN', (0, r_idx), (10, r_idx)))
            table_styles.append(('BACKGROUND', (0, r_idx), (10, r_idx), colors.HexColor('#F8F9FA')))
            
    elif sub_type == "印刷外発注":
        table_content.append([
            Paragraph("用途", header_cell_style), Paragraph("納品先", header_cell_style),
            Paragraph("用紙銘柄", header_cell_style), Paragraph("印刷サイズ", header_cell_style),
            Paragraph("斤量", header_cell_style), Paragraph("目", header_cell_style),
            Paragraph("通数", header_cell_style), Paragraph("頁数", header_cell_style),
            Paragraph("表/裏", header_cell_style), Paragraph("台/版", header_cell_style),
            Paragraph("納入日", header_cell_style)
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
            r_idx = len(table_content)
            table_content.append([Paragraph(f"<b>備考:</b> {row.get('備考', '')}", cell_style)] + [''] * 10)
            table_styles.append(('SPAN', (0, r_idx), (10, r_idx)))
            table_styles.append(('BACKGROUND', (0, r_idx), (10, r_idx), colors.HexColor('#F8F9FA')))

    elif sub_type == "製本外発注":
        table_content.append([
            Paragraph("用途", header_cell_style), Paragraph("納品先", header_cell_style),
            Paragraph("製本", header_cell_style), Paragraph("加工", header_cell_style),
            Paragraph("詳細", header_cell_style), Paragraph("部数", header_cell_style),
            Paragraph("納入日", header_cell_style), Paragraph("時間", header_cell_style),
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
            r_idx = len(table_content)
            table_content.append([Paragraph(f"<b>備考:</b> {row.get('備考', '')}", cell_style)] + [''] * 10)
            table_styles.append(('SPAN', (0, r_idx), (10, r_idx)))
            table_styles.append(('BACKGROUND', (0, r_idx), (10, r_idx), colors.HexColor('#F8F9FA')))

    elif sub_type == "その他外発注":
        table_content.append([
            Paragraph("納品先", header_cell_style), Paragraph("数量", header_cell_style),
            Paragraph("仕入単価", header_cell_style), Paragraph("合計金額", header_cell_style),
            Paragraph("納入日", header_cell_style), Paragraph("時間", header_cell_style),
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
            req_idx = len(table_content)
            table_content.append([Paragraph(f"<b>依頼内容:</b> {row.get('作業内容・仕様', '')}", cell_style)] + [''] * 10)
            table_styles.append(('SPAN', (0, req_idx), (10, req_idx)))
            table_styles.append(('BACKGROUND', (0, req_idx), (10, req_idx), colors.HexColor('#F8F9FA')))
            
            rem_idx = len(table_content)
            table_content.append([Paragraph(f"<b>備考:</b> {row.get('備考', '')}", cell_style)] + [''] * 10)
            table_styles.append(('SPAN', (0, rem_idx), (10, rem_idx)))
            table_styles.append(('BACKGROUND', (0, rem_idx), (10, rem_idx), colors.HexColor('#F8F9FA')))

    t_main = Table(table_content, colWidths=col_widths)
    t_main.setStyle(TableStyle(table_styles))
    
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
    st.info("💡 指定した期間（開始日〜終了日）のデータを新着順に最大500件まで効率よく取得して集計します。")
    
    col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
    with col_f1:
        start_date = st.date_input("開始日", value=date.today().replace(day=1))
    with col_f2:
        end_date = st.date_input("終了日", value=date.today())
    with col_f3:
        st.markdown("<br>", unsafe_allow_html=True)
        run_summary = st.button("🔄 指定期間のデータを取得して集計を実行", type="primary")
        
    if run_summary:
        with st.spinner("サーバーからデータを取得・集計中..."):
            # 指定された期間を文字列に変換してクエリ検索
            start_str = start_date.strftime("%Y-%m-%d") if start_date else None
            end_str = end_date.strftime("%Y-%m-%d") if end_date else None
            
            all_records = fetch_records_with_query(start_d=start_str, end_d=end_str, limit_count=500)
            
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
                            delivery_date_str = d.get("納入日", "")
                            
                            # アプリ側でも念のため期間内か厳密にチェック
                            if start_date or end_date:
                                if delivery_date_str:
                                    try:
                                        d_date = datetime.strptime(str(delivery_date_str)[:10], "%Y-%m-%d").date()
                                        if start_date and d_date < start_date:
                                            continue
                                        if end_date and d_date > end_date:
                                            continue
                                    except ValueError:
                                        pass
                                        
                            summary_list.append({
                                "受注番号": order_no,
                                "得意先名": customer,
                                "営業担当": staff,
                                "発注種別": label,
                                "発注先": d.get("発注先", "未指定"),
                                "納入日": delivery_date_str,
                                "明細詳細": str(d)
                            })
                
                if summary_list:
                    df_summary = pd.DataFrame(summary_list)
                    st.success(f"✅ 集計完了！条件に一致する全 {len(df_summary)} 件の外発注明細を検出しました。")
                    
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        st.markdown("#### 👤 営業担当者別発注件数")
                        st.dataframe(df_summary['営業担当'].value_counts().reset_index(), use_container_width=True)
                    with col_s2:
                        st.markdown("#### 🏢 得意先別発注件数")
                        st.dataframe(df_summary['得意先名'].value_counts().reset_index(), use_container_width=True)
                        
                    st.markdown("#### 📋 検出された全明細データ一覧")
                    st.dataframe(df_summary, use_container_width=True)
                else:
                    st.warning("⚠️ 指定した期間内に有効な外発注明細データが見つかりませんでした。")
            else:
                st.error("❌ レコードの取得に失敗しました。APIの接続状態をご確認ください。")