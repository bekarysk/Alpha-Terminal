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
</style>
""", unsafe_allow_html=True)

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
        
    if submitted:
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
    if hist_df.empty:
        st.error(f"Не удалось выгрузить отчетность для тикера {ticker}.")
        st.stop()

    with st.sidebar:
        wacc_input = st.slider("WACC (%)", 6.0, 15.0, round(data["wacc"] * 100, 1), 0.1) / 100.0
        default_growth = round(data["smart_growth_est"] * 100, 1)
        growth_input = st.slider("Рост FCF (1–5 г., %)", -10.0, 75.0, default_growth, 0.5) / 100.0
        term_input = st.slider("Терминальный рост (%)", 2.0, 4.5, 3.5, 0.1) / 100.0

    base_fcf = data["latest_true_fcf"] if use_true_fcf else data["latest_std_fcf"]
    fair_price = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input, growth_input, term_input)
    implied_growth = calculate_reverse_dcf(data["price"], base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input, term_input)
    upside = ((fair_price - data["price"]) / data["price"] * 100) if data["price"] > 0 else 0

    score, recommendation, flags = generate_forensic_audit_and_memo(data, fair_price, implied_growth)

    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 1. Оценка & Рекомендация",
        "🔥 2. Рентген Портфеля",
        "🕵️‍♂️ 3. Инсайдеры",
        "🧠 4. Форензик & PDF Отчет"
    ])

    # ==================== TAB 1 ====================
    with tab1:
        try:
            st.subheader(f"{data['name']} ({ticker}) — {data['industry']}")
            
            rec_color_map = {
                "STRONG BUY": "🟢 **STRONG BUY**",
                "RECOMMEND / BUY": "🟢 **BUY / ACCUMULATE**",
                "HOLD / WATCH": "🟡 **HOLD / WATCH**",
                "DO NOT BUY / AVOID": "🔴 **DO NOT BUY / AVOID**"
            }
            st.markdown(f"### Рекомендация терминала: {rec_color_map.get(recommendation, recommendation)}")

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Цена", f"${data['price']:,.2f}")
            c2.metric("Справедливая цена", f"${fair_price:,.2f}", f"{upside:+.1f}%")
            c3.metric("Reverse DCF", f"{(implied_growth or 0)*100:.1f}% /г")
            c4.metric("Rule of 40", f"{data['rule_of_40']:.1f}%")
            c5.metric("Truth Score", f"{score}/100")

            st.divider()
            left_col, right_col = st.columns([3, 2])

            with left_col:
                st.markdown(f"#### 🕵️‍♂️ Денежные потоки: {ticker}")
                fig = go.Figure()
                fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["Net Income"]/1e9, name="Net Income", marker_color="#58a6ff"))
                fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["Standard FCF"]/1e9, name="Standard FCF", marker_color="#3fb950"))
                fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["True FCF"]/1e9, name="True FCF (минус SBC)", marker_color="#d29922"))
                fig.update_layout(barmode="group", template="plotly_dark", yaxis_title="$B", height=350, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig, use_container_width=True)

            with right_col:
                st.markdown("#### 📊 Сценарии оценки")
                if base_fcf > 0:
                    bear_p = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input + 0.015, growth_input * 0.75, term_input)
                    bull_p = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], max(wacc_input - 0.01, 0.065), growth_input * 1.20, term_input)
                    scen_fig = go.Figure(go.Bar(
                        x=["Bear", "Рынок", "DCF", "Bull"],
                        y=[bear_p, data["price"], fair_price, bull_p],
                        marker_color=["#f85149", "#8b949e", "#58a6ff", "#3fb950"],
                        text=[f"${p:,.1f}" for p in [bear_p, data["price"], fair_price, bull_p]],
                        textposition="auto"
                    ))
                    scen_fig.update_layout(template="plotly_dark", yaxis_title="Цена ($)", height=350, margin=dict(l=20, r=20, t=20, b=20))
                    st.plotly_chart(scen_fig, use_container_width=True)
        except Exception as e:
            st.error(f"Ошибка во вкладке 1: {e}")

    # ==================== TAB 2 ====================
    with tab2:
        try:
            st.markdown("### 🔥 Рентген Портфеля")
            tickers = [t.strip().upper() for t in pool_input.split(",") if t.strip()]
            if tickers:
                with st.spinner("Сканируем портфель..."):
                    xray_df = analyze_portfolio_xray(tickers)
                if not xray_df.empty:
                    st.dataframe(xray_df, use_container_width=True, hide_index=True)
                else:
                    st.warning("Не удалось загрузить данные для портфеля.")
        except Exception as e:
            st.error(f"Ошибка в рентгене портфеля: {e}")

    # ==================== TAB 3 ====================
    with tab3:
        try:
            st.markdown(f"### 🕵️‍♂️ Инсайдеры: {ticker}")
            ins_df = fetch_insider_activity(ticker)
            if not ins_df.empty and "Status" not in ins_df.columns:
                st.dataframe(ins_df, use_container_width=True, hide_index=True)
            else:
                st.info("Нет недавних открытых транзакций инсайдеров Form 4 в свободном доступе.")
        except Exception as e:
            st.info("Информация по инсайдерам временно недоступна для этого тикера.")

    # ==================== TAB 4 ====================
    with tab4:
        try:
            st.markdown(f"### 🧠 Форензик-Аудит & PDF Отчет: {ticker}")
            st.progress(score / 100.0, text=f"Truth Score: {score}/100 — Рекомендация: {recommendation}")
            
            for title, desc in flags:
                with st.container(border=True):
                    st.markdown(f"**{title}** — {desc}")
                    
            st.divider()
            st.markdown("#### 📄 Скачать официальный отчет в PDF")
            pdf_bytes = generate_pdf_report(data, fair_price, implied_growth, score, recommendation, flags)
            
            st.download_button(
                label="📥 Скачать красивый PDF-отчет",
                data=pdf_bytes,
                file_name=f"{ticker}_Investment_Report.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"Ошибка во вкладке 4: {e}")

except Exception as e:
    st.error(f"Критическая ошибка загрузки терминала: {e}")
