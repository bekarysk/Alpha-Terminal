import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from valuation_engine import (
    fetch_company_data,
    analyze_portfolio_xray,
    calculate_dcf,
    calculate_reverse_dcf,
    fetch_insider_activity,
    generate_forensic_audit_and_memo,
    generate_pdf_report
)

st.set_page_config(page_title="Alpha Valuation Terminal v1.0", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; }
    div[data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 14px;
        border-radius: 10px;
    }
    .alpha-table {
        width: 100%;
        border-collapse: collapse;
        margin: 12px 0;
        font-size: 0.92rem;
        background-color: #0d1117;
        color: #e6edf3;
        border: 1px solid #30363d;
        border-radius: 8px;
        overflow: hidden;
    }
    .alpha-table th {
        background-color: #161b22;
        color: #58a6ff;
        text-align: left;
        padding: 10px 14px;
        border-bottom: 1px solid #30363d;
        font-weight: 600;
    }
    .alpha-table td {
        padding: 9px 14px;
        border-bottom: 1px solid #21262d;
    }
    .alpha-table tr:hover {
        background-color: #161b22;
    }
</style>
""", unsafe_allow_html=True)

def render_dark_table(df):
    """Отрисовка таблицы в чистом HTML без использования JS-бандлов st.dataframe, которые падают в Safari/Cloud."""
    if df is None or df.empty:
        st.info("Нет данных для отображения.")
        return
    html_table = df.to_html(index=False, classes="alpha-table", border=0)
    st.markdown(html_table, unsafe_allow_html=True)

st.title("⚡ Alpha Terminal v1.0 — Institutional Tech Valuation & Forensic Suite")
st.caption("10-Year 2-Stage Damodaran DCF • SBC Dilution X-Ray • Portfolio Stress-Tester • PDF Export")

with st.sidebar:
    st.header("🔍 Управление терминалом")
    with st.form("ticker_form"):
        ticker_input = st.text_input("Основной тикер (США)", value="MSFT").upper().strip()
        use_true_fcf = st.toggle("Считать по True FCF (минус SBC)", value=True)
        submitted = st.form_submit_button("🚀 Анализировать тикер")
        
    if "active_ticker" not in st.session_state:
        st.session_state.active_ticker = "MSFT"
        
    if submitted and ticker_input:
        st.session_state.active_ticker = ticker_input

    ticker = st.session_state.active_ticker

    st.divider()
    st.subheader("💼 Конструктор Портфеля")
    pool_input = st.text_area("Тикеры портфеля (через запятую)", value="MSFT, NVDA, AAPL, AMZN, GOOGL")
    portfolio_capital = st.number_input("Размер капитала портфеля ($)", min_value=1000, value=100000, step=5000)
    
    st.divider()
    st.subheader("🎛️ Калибровка 10Y DCF")

try:
    with st.spinner(f"Загружаем институциональную модель для {ticker}..."):
        data = fetch_company_data(ticker)
        
    hist_df = data["history"]

    with st.sidebar:
        wacc_default = float(round(data["wacc"] * 100, 1))
        growth_default = float(round(data["smart_growth_est"] * 100, 1))
        wacc_input = st.slider("WACC (%)", 6.0, 15.0, min(max(wacc_default, 6.0), 15.0), 0.1, key=f"wacc_{ticker}") / 100.0
        growth_input = st.slider("Рост FCF (1–5 г., %)", -10.0, 45.0, min(max(growth_default, -10.0), 45.0), 0.5, key=f"g_{ticker}") / 100.0
        term_input = st.slider("Терминальный рост (%)", 2.0, 4.5, 3.5, 0.1, key=f"term_{ticker}") / 100.0
        st.caption(f"Акций в обращении: **{data['shares']/1e9:.2f}B**")
        st.caption(f"Безрисковая ставка 10Y US: **{data['rf']*100:.2f}%**")

    base_fcf = data["latest_true_fcf"] if use_true_fcf else data["latest_std_fcf"]
    fair_price = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input, growth_input, term_input)
    implied_growth = calculate_reverse_dcf(data["price"], base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input, term_input)
    upside = ((fair_price - data["price"]) / data["price"] * 100.0) if data["price"] > 0 else 0.0

    score, recommendation, flags = generate_forensic_audit_and_memo(data, fair_price, implied_growth)

    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 1. Оценка & Рекомендация",
        "🔥 2. Рентген Портфеля",
        "🕵️‍♂️ 3. Инсайдеры",
        "🧠 4. Форензик & PDF Отчет"
    ])

    # ==================== ВКЛАДКА 1 ====================
    with tab1:
        st.subheader(f"{data['name']} ({ticker}) — {data['industry']}")
        
        rec_color_map = {
            "STRONG BUY": "🟢 **STRONG BUY**",
            "RECOMMEND / BUY": "🟢 **RECOMMEND / BUY**",
            "HOLD / WATCH": "🟡 **HOLD / WATCH**",
            "DO NOT BUY / AVOID": "🔴 **DO NOT BUY / AVOID**"
        }
        st.markdown(f"### Рекомендация терминала: {rec_color_map.get(recommendation, recommendation)}")

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Цена акции", f"${data['price']:,.2f}", f"Target: ${data['target_mean_price']:,.0f}")
        c2.metric("Справедливая цена", f"${fair_price:,.2f}" if fair_price > 0 else "N/A", f"{upside:+.1f}% к рынку")
        c3.metric("Reverse DCF", f"{(implied_growth or 0)*100:.1f}% /г", f"Модель: {growth_input*100:.1f}%", delta_color="off")
        c4.metric("Rule of 40", f"{data['rule_of_40']:.1f}%", "Лидер (>40%)" if data['rule_of_40'] >= 40 else "Ниже 40%")
        c5.metric("Truth Score", f"{score}/100", f"Z-Score: {data['z_score']:.1f}")

        st.divider()
        left_col, right_col = st.columns([3, 2])

        with left_col:
            st.markdown(f"#### 🕵️‍♂️ Денежные потоки: {ticker} ($B)")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["Net Income"]/1e9, name="Net Income (GAAP)", marker_color="#58a6ff"))
            fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["Standard FCF"]/1e9, name="Standard FCF", marker_color="#3fb950"))
            fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["True FCF"]/1e9, name="True FCF (минус SBC)", marker_color="#d29922"))
            fig.update_layout(barmode="group", template="plotly_dark", yaxis_title="Миллиарды USD ($B)", height=350, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

        with right_col:
            st.markdown("#### 📊 Сценарии справедливой цены ($)")
            if base_fcf > 0:
                bear_p = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input + 0.015, growth_input * 0.75, term_input)
                bull_p = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], max(wacc_input - 0.01, 0.065), min(growth_input * 1.25, 0.40), term_input)
                scen_fig = go.Figure(go.Bar(
                    x=["Bear", "Рынок", "Твой DCF", "Wall St", "Bull"],
                    y=[bear_p, data["price"], fair_price, data["target_mean_price"], bull_p],
                    marker_color=["#f85149", "#8b949e", "#58a6ff", "#a371f7", "#3fb950"],
                    text=[f"${p:,.0f}" for p in [bear_p, data["price"], fair_price, data["target_mean_price"], bull_p]],
                    textposition="auto"
                ))
                scen_fig.update_layout(template="plotly_dark", yaxis_title="Цена акции ($)", height=350, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(scen_fig, use_container_width=True)

        st.markdown(f"#### 📂 Финансовая таблица по годам: {ticker}")
        display_df = hist_df[["Year", "Revenue", "Net Income", "Standard FCF", "SBC", "True FCF", "SBC % of Rev", "True FCF Margin %"]].copy()
        for col in ["Revenue", "Net Income", "Standard FCF", "SBC", "True FCF"]:
            display_df[col] = display_df[col].apply(lambda x: f"${x/1e9:,.2f}B")
        for col in ["SBC % of Rev", "True FCF Margin %"]:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}%")
        render_dark_table(display_df)

    # ==================== ВКЛАДКА 2 ====================
    with tab2:
        st.markdown("### 🔥 Рентген Портфеля & Стресс-Тест")
        st.caption(f"Распределение капитала **${portfolio_capital:,.0f}** по выбранным технологическим активам с учетом размытия SBC:")
        tickers_list = [t.strip().upper() for t in pool_input.split(",") if t.strip()]
        if tickers_list:
            xray_df = analyze_portfolio_xray(tickers_list)
            render_dark_table(xray_df)
        else:
            st.warning("Введите хотя бы один тикер в Конструктор Портфеля слева.")

    # ==================== ВКЛАДКА 3 ====================
    with tab3:
        st.markdown(f"### 🕵️‍♂️ Структура владения и активность инсайдеров: {ticker}")
        ic1, ic2, ic3 = st.columns(3)
        ic1.metric("Институциональные фонды", f"{data['inst_ownership']*100:.1f}%")
        ic2.metric("Владение инсайдеров", f"{data['insider_ownership']*100:.2f}%")
        ic3.metric("Short Float (Шорты)", f"{data['short_ratio']*100:.2f}%")
        
        st.markdown("#### 📋 Последние транзакции Form 4 / Институциональный поток")
        ins_df = fetch_insider_activity(ticker)
        render_dark_table(ins_df)

    # ==================== ВКЛАДКА 4 ====================
    with tab4:
        st.markdown(f"### 🧠 Форензик-Аудит 10-K/10-Q & PDF Отчет: {ticker}")
        st.progress(min(max(score, 0), 100) / 100.0, text=f"Truth Score: {score}/100 — Вердикт: {recommendation}")
        
        for title, desc in flags:
            st.markdown(f"- **{title}** — {desc}")
                
        st.divider()
        st.markdown("#### 📄 Официальный инвестиционный меморандум (PDF)")
        pdf_bytes = generate_pdf_report(data, fair_price, implied_growth, score, recommendation, flags)
        
        st.download_button(
            label=f"📥 Скачать PDF-отчет по {ticker} ({recommendation})",
            data=pdf_bytes,
            file_name=f"{ticker}_Alpha_Terminal_Report.pdf",
            mime="application/pdf"
        )

except Exception as e:
    st.error(f"Ошибка выполнения: {e}")
