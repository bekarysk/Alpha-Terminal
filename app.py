import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from valuation_engine import (
    fetch_company_data,
    analyze_portfolio_xray,
    calculate_dcf,
    calculate_reverse_dcf,
    build_sensitivity_matrix,
    generate_investment_thesis,
    fetch_insider_activity,
    generate_forensic_audit_and_memo,
    generate_pdf_report
)

st.set_page_config(page_title="Alpha Valuation Terminal v2.0", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .block-container { padding-top: 1.1rem; }
    div[data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 13px;
        border-radius: 10px;
    }
    .alpha-table {
        width: 100%;
        border-collapse: collapse;
        margin: 10px 0;
        font-size: 0.90rem;
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
        padding: 9px 12px;
        border-bottom: 1px solid #30363d;
        font-weight: 600;
    }
    .alpha-table td {
        padding: 8px 12px;
        border-bottom: 1px solid #21262d;
    }
    .alpha-table tr:hover {
        background-color: #161b22;
    }
    .thesis-box-buy {
        background-color: rgba(46, 160, 67, 0.10);
        border-left: 4px solid #3fb950;
        padding: 14px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    .thesis-box-avoid {
        background-color: rgba(248, 81, 73, 0.10);
        border-left: 4px solid #f85149;
        padding: 14px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
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
    lang_choice = st.radio("🌐 Language / Язык", ["English", "Русский"], horizontal=True)
    lang = "EN" if lang_choice == "English" else "RU"
    
    st.header("🔍 Terminal Control" if lang == "EN" else "🔍 Управление терминалом")
    with st.form("ticker_form"):
        ticker_input = st.text_input(
            "Primary US Ticker" if lang == "EN" else "Основной тикер (США)",
            value="MSFT"
        ).upper().strip()
        use_true_fcf = st.toggle(
            "Use True FCF (deduct SBC)" if lang == "EN" else "Считать по True FCF (минус SBC)",
            value=True
        )
        submitted = st.form_submit_button("🚀 Run Institutional Analysis" if lang == "EN" else "🚀 Анализировать тикер")
        
    if "active_ticker" not in st.session_state:
        st.session_state.active_ticker = "MSFT"
        
    if submitted and ticker_input:
        st.session_state.active_ticker = ticker_input

    ticker = st.session_state.active_ticker

    st.divider()
    st.subheader("💼 Portfolio Constructor" if lang == "EN" else "💼 Конструктор Портфеля")
    pool_input = st.text_area(
        "Portfolio Tickers (comma-separated)" if lang == "EN" else "Тикеры портфеля (через запятую)",
        value="MSFT, NVDA, AAPL, AMZN, GOOGL"
    )
    portfolio_capital = st.number_input(
        "Portfolio Capital ($)" if lang == "EN" else "Размер капитала портфеля ($)",
        min_value=1000, value=100000, step=5000
    )
    
    st.divider()
    st.subheader("🎛️ 10Y DCF Calibration" if lang == "EN" else "🎛️ Калибровка 10Y DCF")

st.title("⚡ Alpha Terminal v2.0 — Institutional Tech Valuation & Forensic Suite")
st.caption(
    "10-Year 2-Stage Damodaran DCF • Why Buy / Why Avoid Thesis Engine • WACC Sensitivity Matrix • Portfolio Stress-Tester • PDF Export"
    if lang == "EN" else
    "10-летняя 2-фазная модель Дамодарана • Генератор тезисов (Почему покупать / избегать) • Матрица чувствительности • Стресс-тест портфеля • PDF"
)

try:
    with st.spinner(f"Loading institutional model for {ticker}..." if lang == "EN" else f"Загружаем институциональную модель для {ticker}..."):
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
            "FCF Growth (Years 1–5, %)" if lang == "EN" else "Рост FCF (1–5 г., %)",
            -10.0, 45.0, min(max(growth_default, -10.0), 45.0), 0.5, key=f"g_{ticker}"
        ) / 100.0
        term_input = st.slider(
            "Terminal Growth (%)" if lang == "EN" else "Терминальный рост (%)",
            2.0, 4.5, 3.5, 0.1, key=f"term_{ticker}"
        ) / 100.0
        st.caption(f"Shares Outstanding: **{data['shares']/1e9:.2f}B** | 10Y US Treasury: **{data['rf']*100:.2f}%**")

    base_fcf = data["latest_true_fcf"] if use_true_fcf else data["latest_std_fcf"]
    fair_price = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input, growth_input, term_input)
    implied_growth = calculate_reverse_dcf(data["price"], base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input, term_input)
    upside = ((fair_price - data["price"]) / data["price"] * 100.0) if data["price"] > 0 else 0.0

    score, recommendation, flags = generate_forensic_audit_and_memo(data, fair_price, implied_growth, lang=lang)
    why_buy, why_not, expect_df = generate_investment_thesis(data, fair_price, implied_growth, wacc_input, growth_input, term_input, lang=lang)

    if lang == "EN":
        tab1, tab2, tab3, tab4 = st.tabs([
            "🎯 1. Valuation, Thesis & What to Expect",
            "🔥 2. Portfolio X-Ray & Stress-Test",
            "🕵️‍♂️ 3. Insiders & Institutional Radar",
            "🧠 4. 10-K Forensic Audit & PDF Memo"
        ])
    else:
        tab1, tab2, tab3, tab4 = st.tabs([
            "🎯 1. Оценка, Тезис & Чего Ожидать",
            "🔥 2. Рентген & Стресс-Тест Портфеля",
            "🕵️‍♂️ 3. Инсайдеры & Институционалы",
            "🧠 4. Форензик-Аудит & PDF Отчет"
        ])

    # ==================== TAB 1 ====================
    with tab1:
        st.subheader(f"{data['name']} ({ticker}) — {data['industry']}")
        
        rec_badge_en = {
            "STRONG BUY": "🟢 **STRONG BUY — High Conviction Accumulation**",
            "RECOMMEND / BUY": "🟢 **RECOMMEND / BUY — Quality Compounder at Reasonable Price**",
            "HOLD / WATCH": "🟡 **HOLD / WATCH — Fairly Priced / Await Better Entry**",
            "DO NOT BUY / AVOID": "🔴 **DO NOT BUY / AVOID — Priced for Perfection or High SBC Dilution**"
        }
        rec_badge_ru = {
            "STRONG BUY": "🟢 **STRONG BUY — Сильная покупка (Фундаментальный апсайд)**",
            "RECOMMEND / BUY": "🟢 **RECOMMEND / BUY — Рекомендуется к покупке**",
            "HOLD / WATCH": "🟡 **HOLD / WATCH — Держать / Ждать коррекции для входа**",
            "DO NOT BUY / AVOID": "🔴 **DO NOT BUY / AVOID — Избегать (Переоценка или размытие SBC)**"
        }
        badge_text = rec_badge_en.get(recommendation, recommendation) if lang == "EN" else rec_badge_ru.get(recommendation, recommendation)
        st.markdown(f"### {'Institutional Verdict' if lang == 'EN' else 'Вердикт терминала'}: {badge_text}")

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Market Price" if lang == "EN" else "Цена акции", f"${data['price']:,.2f}", f"Wall St: ${data['target_mean_price']:,.0f}")
        c2.metric("Fair Value (10Y DCF)" if lang == "EN" else "Справедливая цена", f"${fair_price:,.2f}" if fair_price > 0 else "N/A", f"{upside:+.1f}%")
        c3.metric("Priced-In Growth (Rev DCF)" if lang == "EN" else "Заложено в цену (Rev DCF)", f"{(implied_growth or 0)*100:.1f}% /yr", f"Model: {growth_input*100:.1f}%", delta_color="off")
        c4.metric("Rule of 40 Index", f"{data['rule_of_40']:.1f}%", "Elite (>40%)" if data['rule_of_40'] >= 40 else "Sub-40%")
        c5.metric("Forensic Truth Score", f"{score}/100", f"Z-Score: {data['z_score']:.1f}")

        st.divider()
        
        # --- NEW SECTION: WHY BUY vs WHY AVOID ---
        st.markdown(f"#### 💡 {'Executive Investment Thesis: Why Buy vs. Why Avoid' if lang == 'EN' else 'Инвестиционный тезис: Почему покупать vs. Почему избегать'}")
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            st.markdown(f"**🟢 {'WHY BUY (Bullish Catalysts & Strengths)' if lang == 'EN' else 'ПОЧЕМУ ПОКУПАТЬ (Сильные стороны и драйверы)'}**")
            if why_buy:
                for b_item in why_buy:
                    st.markdown(f"<div class='thesis-box-buy'>{b_item}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='thesis-box-buy'>{'Current valuation multiples and cash conversion require a significant pullback before initiating a position.' if lang == 'EN' else 'Текущие мультипликаторы требуют коррекции цены перед открытием позиции.'}</div>", unsafe_allow_html=True)

        with t_col2:
            st.markdown(f"**🔴 {'WHY NOT / AVOID (Key Risks & Red Flags)' if lang == 'EN' else 'ПОЧЕМУ НЕ ПОКУПАТЬ (Риски и слабые стороны)'}**")
            if why_not:
                for n_item in why_not:
                    st.markdown(f"<div class='thesis-box-avoid'>{n_item}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='thesis-box-avoid'>{'No major fundamental or forensic red flags detected at current valuation levels.' if lang == 'EN' else 'Фундаментальных и форензик красных флагов на текущих уровнях не выявлено.'}</div>", unsafe_allow_html=True)

        st.divider()
        
        # --- NEW SECTION: WHAT TO EXPECT (SCENARIO OUTLOOK) ---
        st.markdown(f"#### 🔮 {'What to Expect: 12–36 Month Scenario Roadmap' if lang == 'EN' else 'Чего ожидать от акции: Сценарный прогноз на 12–36 месяцев'}")
        render_dark_table(expect_df)

        st.divider()
        left_col, right_col = st.columns([3, 2])

        with left_col:
            st.markdown(f"#### 🕵️‍♂️ {'Cash Flow Quality: GAAP vs. True FCF ($B)' if lang == 'EN' else 'Динамика денежных потоков: GAAP vs. True FCF ($B)'}")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["Net Income"]/1e9, name="Net Income (GAAP)", marker_color="#58a6ff"))
            fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["Standard FCF"]/1e9, name="Standard FCF", marker_color="#3fb950"))
            fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["True FCF"]/1e9, name="True FCF (ex-SBC)", marker_color="#d29922"))
            fig.update_layout(barmode="group", template="plotly_dark", yaxis_title="USD Billions ($B)", height=350, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

        with right_col:
            st.markdown(f"#### 📊 {'Valuation Corridor ($)' if lang == 'EN' else 'Коридор справедливой цены ($)'}")
            if base_fcf > 0:
                bear_p = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input + 0.015, growth_input * 0.70, term_input)
                bull_p = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], max(wacc_input - 0.01, 0.065), min(growth_input * 1.25, 0.42), term_input)
                scen_fig = go.Figure(go.Bar(
                    x=["Bear", "Market" if lang == "EN" else "Рынок", "True DCF", "Wall St", "Bull"],
                    y=[bear_p, data["price"], fair_price, data["target_mean_price"], bull_p],
                    marker_color=["#f85149", "#8b949e", "#58a6ff", "#a371f7", "#3fb950"],
                    text=[f"${p:,.0f}" for p in [bear_p, data["price"], fair_price, data["target_mean_price"], bull_p]],
                    textposition="auto"
                ))
                scen_fig.update_layout(template="plotly_dark", yaxis_title="Share Price ($)", height=350, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(scen_fig, use_container_width=True)

        st.markdown(f"#### 🎯 {'Institutional Sensitivity Matrix (WACC vs. 5Y FCF Growth)' if lang == 'EN' else 'Матрица чувствительности (WACC vs. Рост FCF)'}")
        sens_df = build_sensitivity_matrix(base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input, growth_input, term_input)
        render_dark_table(sens_df)

        st.markdown(f"#### 📂 {'Multi-Year Financial Breakdown' if lang == 'EN' else 'Финансовая таблица по годам'}: {ticker}")
        display_df = hist_df[["Year", "Revenue", "Net Income", "Standard FCF", "SBC", "True FCF", "SBC % of Rev", "True FCF Margin %"]].copy()
        for col in ["Revenue", "Net Income", "Standard FCF", "SBC", "True FCF"]:
            display_df[col] = display_df[col].apply(lambda x: f"${x/1e9:,.2f}B")
        for col in ["SBC % of Rev", "True FCF Margin %"]:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}%")
        render_dark_table(display_df)

    # ==================== TAB 2 ====================
    with tab2:
        st.markdown(f"### 🔥 {'Portfolio X-Ray, Capital Allocation & Macro Stress-Tester' if lang == 'EN' else 'Рентген Портфеля, Аллокация Капитала & Макро Стресс-Тест'}")
        tickers_list = [t.strip().upper() for t in pool_input.split(",") if t.strip()]
        if tickers_list:
            xray_df, p_sum = analyze_portfolio_xray(tickers_list, capital=portfolio_capital, lang=lang)
            if p_sum:
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("Total Capital" if lang == "EN" else "Капитал портфеля", f"${portfolio_capital:,.0f}")
                p2.metric("Weighted DCF Upside" if lang == "EN" else "Средний потенциал DCF", f"{p_sum['weighted_upside']:+.1f}%")
                p3.metric("Portfolio Beta" if lang == "EN" else "Бета портфеля", f"{p_sum['weighted_beta']:.2f}")
                p4.metric("-20% Nasdaq Shock Impact" if lang == "EN" else "Шок при падении рынка на -20%", f"${p_sum['stress_loss_usd']:,.0f} ({p_sum['stress_drop_pct']:.1f}%)")
            render_dark_table(xray_df)
        else:
            st.warning("Please enter at least one ticker in the sidebar." if lang == "EN" else "Введите хотя бы один тикер в боковой панели.")

    # ==================== TAB 3 ====================
    with tab3:
        st.markdown(f"### 🕵️‍♂️ {'Ownership Structure & Insider Form 4 Activity' if lang == 'EN' else 'Структура владения и активность инсайдеров'}: {ticker}")
        ic1, ic2, ic3 = st.columns(3)
        ic1.metric("Institutional Ownership" if lang == "EN" else "Институциональные фонды", f"{data['inst_ownership']*100:.1f}%")
        ic2.metric("Insider Ownership" if lang == "EN" else "Владение инсайдеров", f"{data['insider_ownership']*100:.2f}%")
        ic3.metric("Short Float" if lang == "EN" else "Короткие позиции (Short Float)", f"{data['short_ratio']*100:.2f}%")
        
        st.markdown(f"#### 📋 {'Recent Form 4 Filings & Institutional Flows' if lang == 'EN' else 'Последние транзакции Form 4 / Институциональный поток'}")
        ins_df = fetch_insider_activity(ticker, lang=lang)
        render_dark_table(ins_df)

    # ==================== TAB 4 ====================
    with tab4:
        st.markdown(f"### 🧠 {'10-K/10-Q Forensic Accounting Audit & Investment Memo' if lang == 'EN' else 'Форензик-Аудит 10-K/10-Q & Инвестиционный Меморандум'}: {ticker}")
        st.progress(min(max(score, 0), 100) / 100.0, text=f"Truth Score: {score}/100 — Verdict: {recommendation}")
        
        for title, desc in flags:
            st.markdown(f"- **{title}** — {desc}")
                
        st.divider()
        st.markdown(f"#### 📄 {'Download Institutional Investment Committee PDF Report' if lang == 'EN' else 'Скачать официальный инвестиционный меморандум (PDF)'}")
        pdf_bytes = generate_pdf_report(data, fair_price, implied_growth, score, recommendation, flags, why_buy, why_not, expect_df)
        
        st.download_button(
            label=f"📥 {'Download Official PDF Report' if lang == 'EN' else 'Скачать PDF-отчет по'} {ticker} ({recommendation})",
            data=pdf_bytes,
            file_name=f"{ticker}_Alpha_Terminal_v2_Report.pdf",
            mime="application/pdf"
        )

except Exception as e:
    st.error(f"Execution error / Ошибка выполнения: {e}")
