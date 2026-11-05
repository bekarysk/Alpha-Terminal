import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from valuation_engine import (
    fetch_company_data,
    analyze_portfolio_xray,
    calculate_dcf,
    calculate_reverse_dcf,
    generate_horizon_forecasts,
    fetch_news_and_sentiment,
    build_sensitivity_matrix,
    generate_investment_thesis,
    fetch_insider_activity,
    generate_forensic_audit_and_memo,
    generate_pdf_report
)

st.set_page_config(page_title="Alpha Terminal v3.0", layout="wide", initial_sidebar_state="expanded")

# Строгий минималистичный институциональный дизайн без визуального шума
st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1440px; }
    h1, h2, h3, h4 { font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif; font-weight: 600; letter-spacing: -0.02em; }
    div[data-testid="stMetric"] {
        background-color: #0d1117;
        border: 1px solid #21262d;
        padding: 14px 16px;
        border-radius: 4px;
    }
    div[data-testid="stMetricValue"] {
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
        font-size: 1.45rem !important;
        font-weight: 600;
    }
    div[data-testid="stExpander"] {
        background-color: #0d1117;
        border: 1px solid #21262d;
        border-radius: 4px;
        margin-top: 6px;
        margin-bottom: 12px;
    }
    .alpha-table {
        width: 100%;
        border-collapse: collapse;
        margin: 8px 0 14px 0;
        font-size: 0.86rem;
        font-family: -apple-system, BlinkMacSystemFont, "Inter", sans-serif;
        background-color: #0d1117;
        color: #c9d1d9;
        border: 1px solid #21262d;
    }
    .alpha-table th {
        background-color: #161b22;
        color: #8b949e;
        text-align: left;
        padding: 9px 12px;
        border-bottom: 1px solid #30363d;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.04em;
    }
    .alpha-table td {
        padding: 8px 12px;
        border-bottom: 1px solid #161b22;
        font-family: "SFMono-Regular", Consolas, monospace;
    }
    .alpha-table tr:hover {
        background-color: #161b22;
    }
    .verdict-banner {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-left: 3px solid #58a6ff;
        padding: 12px 16px;
        border-radius: 4px;
        margin-bottom: 16px;
        font-size: 0.95rem;
    }
    .thesis-card-pos {
        background-color: #0d1117;
        border: 1px solid #21262d;
        border-left: 3px solid #2ea043;
        padding: 10px 14px;
        margin-bottom: 8px;
        font-size: 0.88rem;
        color: #c9d1d9;
    }
    .thesis-card-neg {
        background-color: #0d1117;
        border: 1px solid #21262d;
        border-left: 3px solid #da3633;
        padding: 10px 14px;
        margin-bottom: 8px;
        font-size: 0.88rem;
        color: #c9d1d9;
    }
</style>
""", unsafe_allow_html=True)

def render_dark_table(df):
    if df is None or df.empty:
        st.info("No data available / Нет данных.")
        return
    html_table = df.to_html(index=False, classes="alpha-table", border=0)
    st.markdown(html_table, unsafe_allow_html=True)

with st.sidebar:
    lang_choice = st.radio("LANGUAGE / ЯЗЫК", ["English", "Русский"], horizontal=True)
    lang = "EN" if lang_choice == "English" else "RU"
    
    st.markdown("#### TERMINAL PARAMETERS" if lang == "EN" else "#### ПАРАМЕТРЫ ТЕРМИНАЛА")
    with st.form("ticker_form"):
        ticker_input = st.text_input(
            "Equity Ticker (US)" if lang == "EN" else "Тикер компании (США)",
            value="MSFT"
        ).upper().strip()
        use_true_fcf = st.toggle(
            "True FCF Mode (Net of SBC)" if lang == "EN" else "Режим True FCF (за вычетом SBC)",
            value=True
        )
        submitted = st.form_submit_button("Execute Analysis" if lang == "EN" else "Выполнить расчет")
        
    if "active_ticker" not in st.session_state:
        st.session_state.active_ticker = "MSFT"
        
    if submitted and ticker_input:
        st.session_state.active_ticker = ticker_input

    ticker = st.session_state.active_ticker

    st.divider()
    st.markdown("#### PORTFOLIO ALLOCATION" if lang == "EN" else "#### АЛЛОКАЦИЯ ПОРТФЕЛЯ")
    pool_input = st.text_area(
        "Constituent Tickers" if lang == "EN" else "Список тикеров (через запятую)",
        value="MSFT, NVDA, AAPL, AMZN, GOOGL"
    )
    portfolio_capital = st.number_input(
        "Total Capital ($)" if lang == "EN" else "Капитал портфеля ($)",
        min_value=1000, value=100000, step=5000
    )
    
    st.divider()
    st.markdown("#### MODEL ASSUMPTIONS" if lang == "EN" else "#### КАЛИБРОВКА МОДЕЛИ DCF")

st.title("ALPHA TERMINAL v3.0")
st.caption(
    "INSTITUTIONAL EQUITY VALUATION, TIME-HORIZON FORECASTING & FORENSIC ACCOUNTING SUITE"
    if lang == "EN" else
    "ИНСТИТУЦИОНАЛЬНАЯ СИСТЕМА ОЦЕНКИ КАПИТАЛА, ВРЕМЕННОГО ПРОГНОЗИРОВАНИЯ И ФОРЕНЗИК-АУДИТА"
)

try:
    with st.spinner(f"Executing quantitative model for {ticker}..." if lang == "EN" else f"Выполняется количественный расчет по {ticker}..."):
        data = fetch_company_data(ticker)
        
    hist_df = data["history"]

    with st.sidebar:
        wacc_default = float(round(data["wacc"] * 100, 1))
        growth_default = float(round(data["smart_growth_est"] * 100, 1))
        wacc_input = st.slider(
            "Discount Rate (WACC %)" if lang == "EN" else "Ставка дисконтирования (WACC %)",
            6.0, 15.0, min(max(wacc_default, 6.0), 15.0), 0.1, key=f"wacc_{ticker}"
        ) / 100.0
        growth_input = st.slider(
            "Stage 1 FCF Growth (Y1–5, %)" if lang == "EN" else "Темп роста FCF (1–5 лет, %)",
            -10.0, 35.0, min(max(growth_default, -10.0), 35.0), 0.5, key=f"g_{ticker}"
        ) / 100.0
        term_input = st.slider(
            "Terminal Growth Rate (%)" if lang == "EN" else "Терминальный рост (%)",
            2.0, 4.5, 3.5, 0.1, key=f"term_{ticker}"
        ) / 100.0
        st.caption(f"Shares: {data['shares']/1e9:.3f}B | US10Y: {data['rf']*100:.2f}% | Vol: {data['volatility']*100:.1f}%")

    base_fcf = data["latest_true_fcf"] if use_true_fcf else data["latest_std_fcf"]
    fair_price = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input, growth_input, term_input)
    implied_growth = calculate_reverse_dcf(data["price"], base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input, term_input)
    upside = ((fair_price - data["price"]) / data["price"] * 100.0) if data["price"] > 0 else 0.0

    news_df, sentiment_score, sentiment_label = fetch_news_and_sentiment(ticker, data, lang=lang)
    score, recommendation, flags = generate_forensic_audit_and_memo(data, fair_price, implied_growth, sentiment_score=sentiment_score, lang=lang)
    why_buy, why_not = generate_investment_thesis(data, fair_price, implied_growth, wacc_input, growth_input, term_input, lang=lang)
    horizon_df = generate_horizon_forecasts(data, fair_price, wacc_input, growth_input, lang=lang)

    if lang == "EN":
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "1. VALUATION & THESIS",
            "2. HORIZON FORECAST & NEWS",
            "3. PORTFOLIO X-RAY",
            "4. OWNERSHIP & INSIDERS",
            "5. FORENSICS & PDF MEMO"
        ])
    else:
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "1. ОЦЕНКА И ИНВЕСТ-ТЕЗИС",
            "2. ПРОГНОЗ ПО ПЕРИОДАМ И НОВОСТИ",
            "3. РЕНТГЕН ПОРТФЕЛЯ",
            "4. ВЛАДЕНИЕ И ИНСАЙДЕРЫ",
            "5. ФОРЕНЗИК И PDF-ОТЧЕТ"
        ])

    # ==================== TAB 1: VALUATION & THESIS ====================
    with tab1:
        st.markdown(f"### {data['name']} ({ticker}) — {data['industry']}")
        st.markdown(
            f"<div class='verdict-banner'><b>{'INSTITUTIONAL RATING' if lang == 'EN' else 'ИНСТИТУЦИОНАЛЬНЫЙ РЕЙТИНГ'}:</b> {recommendation} &nbsp;|&nbsp; "
            f"<b>{'NEWS SENTIMENT' if lang == 'EN' else 'НОВОСТНОЙ СЕНТИМЕНТ'}:</b> {sentiment_label} ({sentiment_score}/100)</div>",
            unsafe_allow_html=True
        )

        # Ряд 1: Основные метрики оценки
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Market Price" if lang == "EN" else "Рыночная цена", f"${data['price']:,.2f}", f"Consensus: ${data['target_mean_price']:,.2f}")
        c2.metric("Intrinsic Value (10Y DCF)" if lang == "EN" else "Справедливая цена (DCF)", f"${fair_price:,.2f}" if fair_price > 0 else "N/A", f"{upside:+.1f}%")
        c3.metric("Implied Growth (Reverse DCF)" if lang == "EN" else "Ожидания рынка (Rev DCF)", f"{(implied_growth or 0)*100:.1f}% /yr", f"Modeled: {growth_input*100:.1f}%", delta_color="off")
        c4.metric("True FCF Yield" if lang == "EN" else "Доходность True FCF", f"{data['fcf_yield']*100:.2f}%", f"P/E: {data['pe_ratio']:.1f}x", delta_color="off")

        # Ряд 2: Качество капитала и эффективность
        k1, k2, k3, k4 = st.columns(4)
        roic_spread = (data["roic"] - wacc_input) * 100.0
        k1.metric("ROIC (Return on Capital)" if lang == "EN" else "Рентабельность капитала (ROIC)", f"{data['roic']*100:.1f}%", f"{roic_spread:+.1f}% vs WACC")
        k2.metric("WACC (Cost of Capital)" if lang == "EN" else "Стоимость капитала (WACC)", f"{wacc_input*100:.1f}%", f"Beta: {data['beta']:.2f}", delta_color="off")
        k3.metric("Rule of 40 Index" if lang == "EN" else "Индекс Rule of 40", f"{data['rule_of_40']:.1f}%", f"Net Margin: {data['net_margin']*100:.1f}%", delta_color="off")
        k4.metric("Forensic Quality Score" if lang == "EN" else "Форензик-индекс качества", f"{score}/100", f"Altman Z: {data['z_score']:.1f}")

        # Скрытый раскрывающийся справочник метрик
        with st.expander("Methodology & Metric Definitions (Click to Expand)" if lang == "EN" else "Справочник метрик и методология расчета (Нажмите для раскрытия)"):
            if lang == "EN":
                st.markdown("""
                * **Intrinsic Value (10Y DCF):** Present value of projected 10-year True Free Cash Flows discounted back to today at WACC. It represents what the share is worth **today**, not a 10-year future price target.
                * **True FCF vs. Standard FCF:** Standard FCF ignores Stock-Based Compensation (SBC). True FCF deducts SBC as a real cash expense to reflect actual cash available to common shareholders.
                * **Implied Growth (Reverse DCF):** The annual FCF growth rate the company must achieve over the next 5 years to justify its current market price. If Implied Growth > Modeled Growth, the stock is priced at a premium.
                * **ROIC vs. WACC:** Return on Invested Capital measures how efficiently the company allocates capital. A company creates economic value only when **ROIC > WACC**.
                * **Rule of 40 Index:** Sum of YoY Revenue Growth (%) and FCF Margin (%). Institutional benchmark for top-tier technology and software businesses is **>40%**.
                * **Altman Z-Score:** Credit-strength test based on working capital, retained earnings, EBIT, and leverage. Above **3.0** indicates a safe balance sheet; below **1.8** signals distress risk.
                """)
            else:
                st.markdown("""
                * **Справедливая цена (Intrinsic Value 10Y DCF):** Приведенная к сегодняшнему дню стоимость будущих 10-летних денежных потоков компании, дисконтированная по ставке WACC. Показывает фундаментальную стоимость акции **прямо сейчас**, а не цену через 10 лет.
                * **True FCF (Очищенный денежный поток):** Стандартный FCF минус вознаграждение сотрудников акциями (`SBC`). Защищает инвестора от скрытого размытия доли.
                * **Ожидания рынка (Reverse DCF):** Темп роста FCF, который уже заложен рынком в текущую цену акции. Если этот показатель значительно выше прогноза модели, акция переоценена.
                * **ROIC vs. WACC:** Рентабельность инвестированного капитала (`ROIC`) в сравнении со стоимостью капитала (`WACC`). Бизнес создает реальную стоимость для акционеров только тогда, когда **ROIC превышает WACC**.
                * **Индекс Rule of 40:** Сумма темпа роста выручки (%) и маржинальности FCF (%). Значение выше **40%** является институциональным стандартом эффективности.
                * **Altman Z-Score:** Индекс кредитной устойчивости баланса. Значение выше **3.0** означает минимальный риск банкротства; ниже **1.8** — зона финансовой уязвимости.
                """)

        st.markdown(f"#### {'Investment Thesis: Bullish Catalysts vs. Risk Factors' if lang == 'EN' else 'Инвестиционный тезис: Факторы покупки vs. Факторы риска'}")
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            st.markdown(f"**{'BULLISH CATALYSTS (WHY BUY)' if lang == 'EN' else 'ФАКТОРЫ ПОКУПКИ (СИЛЬНЫЕ СТОРОНЫ)'}**")
            for b_item in why_buy:
                st.markdown(f"<div class='thesis-card-pos'>{b_item}</div>", unsafe_allow_html=True)
        with t_col2:
            st.markdown(f"**{'KEY RISK FACTORS (WHY AVOID)' if lang == 'EN' else 'ФАКТОРЫ РИСКА (ПОЧЕМУ СТОИТ ИЗБЕГАТЬ)'}**")
            for n_item in why_not:
                st.markdown(f"<div class='thesis-card-neg'>{n_item}</div>", unsafe_allow_html=True)

        left_col, right_col = st.columns([3, 2])
        with left_col:
            st.markdown(f"#### {'Historical Cash Flow Progression ($B)' if lang == 'EN' else 'Динамика денежных потоков по годам ($B)'}")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["Net Income"]/1e9, name="GAAP Net Income", marker_color="#388bfd"))
            fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["Standard FCF"]/1e9, name="Standard FCF", marker_color="#2ea043"))
            fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["True FCF"]/1e9, name="True FCF (ex-SBC)", marker_color="#d29922"))
            fig.update_layout(barmode="group", template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117", yaxis_title="USD Billions ($B)", height=330, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

        with right_col:
            st.markdown(f"#### {'Valuation Scenario Benchmarks ($)' if lang == 'EN' else 'Сравнение сценариев оценки ($)'}")
            if base_fcf > 0:
                bear_p = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input + 0.015, growth_input * 0.70, term_input)
                bull_p = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], max(wacc_input - 0.01, 0.065), min(growth_input * 1.25, 0.35), term_input)
                scen_fig = go.Figure(go.Bar(
                    x=["Bear", "Market" if lang == "EN" else "Рынок", "True DCF", "Consensus", "Bull"],
                    y=[bear_p, data["price"], fair_price, data["target_mean_price"], bull_p],
                    marker_color=["#da3633", "#6e7681", "#388bfd", "#8957e5", "#2ea043"],
                    text=[f"${p:,.1f}" for p in [bear_p, data["price"], fair_price, data["target_mean_price"], bull_p]],
                    textposition="auto"
                ))
                scen_fig.update_layout(template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117", yaxis_title="Share Price ($)", height=330, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(scen_fig, use_container_width=True)

        st.markdown(f"#### {'WACC × Growth Sensitivity Matrix' if lang == 'EN' else 'Матрица чувствительности справедливой цены (WACC × Рост FCF)'}")
        sens_df = build_sensitivity_matrix(base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input, growth_input, term_input)
        render_dark_table(sens_df)
        with st.expander("How to Read the Sensitivity Matrix" if lang == "EN" else "Как читать матрицу чувствительности"):
            st.caption(
                "Shows how the intrinsic value per share changes across 25 combinations of Discount Rate (WACC) and 5-year FCF growth rates. The center cell represents your active baseline model."
                if lang == "EN" else
                "Таблица показывает, как меняется справедливая цена акции при 25 различных комбинациях ставки дисконтирования (WACC) и темпов роста FCF. Центральная ячейка соответствует вашим текущим настройкам."
            )

    # ==================== TAB 2: HORIZON FORECAST & NEWS ====================
    with tab2:
        st.markdown(f"### {'Multi-Horizon Price Trajectory & Market Intelligence' if lang == 'EN' else 'Прогноз траектории цены по интервалам и Мониторинг новостей'}: {ticker}")
        
        if not horizon_df.empty:
            h_col1, h_col2 = st.columns([3, 2])
            with h_col1:
                st.markdown(f"#### {'Projected Price Corridor (1M to 10Y)' if lang == 'EN' else 'Прогнозный коридор цены (от 1 месяца до 10 лет)'}")
                x_col = "Time Horizon" if lang == "EN" else "Временной интервал"
                traj_fig = go.Figure()
                traj_fig.add_trace(go.Scatter(x=horizon_df[x_col], y=horizon_df["Raw_High"], mode="lines+markers", name="Optimistic (High)", line=dict(color="#2ea043", dash="dot")))
                traj_fig.add_trace(go.Scatter(x=horizon_df[x_col], y=horizon_df["Raw_Base"], mode="lines+markers", name="Base Forecast", line=dict(color="#388bfd", width=3)))
                traj_fig.add_trace(go.Scatter(x=horizon_df[x_col], y=horizon_df["Raw_Low"], mode="lines+markers", name="Conservative (Low)", line=dict(color="#da3633", dash="dot")))
                traj_fig.update_layout(template="plotly_dark", paper_bgcolor="#0d1117", plot_bgcolor="#0d1117", yaxis_title="Projected Share Price ($)", height=340, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(traj_fig, use_container_width=True)
                
            with h_col2:
                st.markdown(f"#### {'Time-Interval Forecast Table' if lang == 'EN' else 'Таблица прогнозов по временным интервалам'}")
                clean_h_df = horizon_df.drop(columns=["Years", "Raw_Low", "Raw_Base", "Raw_High"])
                render_dark_table(clean_h_df)
                
            with st.expander("Forecasting Methodology (Mean-Reversion + Drift)" if lang == "EN" else "Методология прогнозирования по временным интервалам"):
                st.caption(
                    "Short-term intervals (1M–6M) are dominated by historical volatility and market momentum. Medium-to-long-term intervals (1Y–10Y) model gradual valuation convergence toward DCF intrinsic value combined with fundamental business compounding."
                    if lang == "EN" else
                    "На коротких интервалах (1–6 мес.) преобладает рыночная волатильность. На горизонтах от 1 до 10 лет модель закладывает постепенное схождение рыночной цены с фундаментальной оценкой DCF и органический рост денежных потоков компании."
                )

        st.divider()
        st.markdown(f"#### {'Real-Time News Feed & Sentiment Scoring' if lang == 'EN' else 'Мониторинг новостей, событий и оценка рыночного сентимента'}")
        st.progress(sentiment_score / 100.0, text=f"{'Aggregate Sentiment Index' if lang == 'EN' else 'Индекс новостного фона'}: {sentiment_score}/100 — {sentiment_label}")
        render_dark_table(news_df)

    # ==================== TAB 3: PORTFOLIO X-RAY ====================
    with tab3:
        st.markdown(f"### {'Portfolio X-Ray, Capital Allocation & Macro Stress-Tester' if lang == 'EN' else 'Рентген портфеля, аллокация капитала и макро стресс-тест'}")
        tickers_list = [t.strip().upper() for t in pool_input.split(",") if t.strip()]
        if tickers_list:
            xray_df, p_sum = analyze_portfolio_xray(tickers_list, capital=portfolio_capital, lang=lang)
            if p_sum:
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("Total Capital" if lang == "EN" else "Капитал портфеля", f"${portfolio_capital:,.0f}")
                p2.metric("Weighted DCF Upside" if lang == "EN" else "Взвешенный потенциал DCF", f"{p_sum['weighted_upside']:+.1f}%")
                p3.metric("Portfolio Beta" if lang == "EN" else "Бета портфеля", f"{p_sum['weighted_beta']:.2f}")
                p4.metric("-20% Market Shock Impact" if lang == "EN" else "Убыток при падении рынка на -20%", f"${p_sum['stress_loss_usd']:,.0f} ({p_sum['stress_drop_pct']:.1f}%)")
            render_dark_table(xray_df)
            with st.expander("Portfolio Stress-Test Methodology" if lang == "EN" else "Как рассчитывается стресс-тест портфеля"):
                st.caption(
                    "Simulates an immediate -20% contraction in the benchmark index and scales each position's drawdown by its historical beta sensitivity."
                    if lang == "EN" else
                    "Моделирует падение широкого рынка (S&P 500 / Nasdaq) на -20% и рассчитывает ожидаемую просадку капитала с учетом коэффициента чувствительности Бета каждой акции."
                )

    # ==================== TAB 4: INSIDERS & OWNERSHIP ====================
    with tab4:
        st.markdown(f"### {'Institutional Ownership & Form 4 Insider Filings' if lang == 'EN' else 'Структура владения и транзакции инсайдеров (Form 4)'}: {ticker}")
        ic1, ic2, ic3 = st.columns(3)
        ic1.metric("Institutional Ownership" if lang == "EN" else "Доля институциональных фондов", f"{data['inst_ownership']*100:.1f}%")
        ic2.metric("Insider Ownership" if lang == "EN" else "Владение инсайдеров", f"{data['insider_ownership']*100:.2f}%")
        ic3.metric("Short Interest (% of Float)" if lang == "EN" else "Короткие позиции (Short Float)", f"{data['short_ratio']*100:.2f}%")
        
        render_dark_table(fetch_insider_activity(ticker, lang=lang))
        
        st.markdown(f"#### {'Historical Financial Statement Summary' if lang == 'EN' else 'Сводка финансовой отчетности по годам'}: {ticker}")
        display_df = hist_df[["Year", "Revenue", "Net Income", "Standard FCF", "SBC", "True FCF", "SBC % of Rev", "True FCF Margin %"]].copy()
        for col in ["Revenue", "Net Income", "Standard FCF", "SBC", "True FCF"]:
            display_df[col] = display_df[col].apply(lambda x: f"${x/1e9:,.2f}B")
        for col in ["SBC % of Rev", "True FCF Margin %"]:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}%")
        render_dark_table(display_df)

    # ==================== TAB 5: FORENSICS & PDF MEMO ====================
    with tab5:
        st.markdown(f"### {'10-K/10-Q Forensic Accounting Audit & Investment Memo' if lang == 'EN' else 'Форензик-аудит отчетности 10-K/10-Q и PDF-меморандум'}: {ticker}")
        st.progress(min(max(score, 0), 100) / 100.0, text=f"Forensic Quality Score: {score}/100 — Rating: {recommendation}")
        
        for title, desc in flags:
            st.markdown(f"<div class='thesis-card-pos' style='border-left-color:#58a6ff;'><b>{title}:</b> {desc}</div>", unsafe_allow_html=True)
                
        st.divider()
        st.markdown(f"#### {'Export Official Investment Committee Memorandum (PDF)' if lang == 'EN' else 'Экспорт официального инвестиционного меморандума (PDF)'}")
        pdf_bytes = generate_pdf_report(data, fair_price, implied_growth, score, recommendation, flags, why_buy, why_not, horizon_df)
        
        st.download_button(
            label=f"{'Download Institutional PDF Report' if lang == 'EN' else 'Скачать PDF-меморандум'} — {ticker} ({recommendation})",
            data=pdf_bytes,
            file_name=f"{ticker}_Alpha_Terminal_v3_Memo.pdf",
            mime="application/pdf"
        )

except Exception as e:
    st.error(f"System Execution Error: {e}")
