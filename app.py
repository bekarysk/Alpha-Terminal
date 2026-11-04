import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from valuation_engine import (
    fetch_company_data,
    analyze_portfolio_xray,
    calculate_dcf,
    calculate_reverse_dcf,
    fetch_insider_activity,
    generate_forensic_audit_and_memo
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
st.caption("10-Year 2-Stage Damodaran DCF • SBC Dilution X-Ray • Portfolio Stress-Tester • Insider & Forensic Audit")

with st.sidebar:
    st.header("🔍 Управление терминалом")
    ticker = st.text_input("Основной тикер (США)", value="NVDA").upper().strip()
    use_true_fcf = st.toggle("Считать по True FCF (минус SBC)", value=True)
    
    st.divider()
    st.subheader("💼 Конструктор Портфеля")
    pool_input = st.text_area("Тикеры портфеля (через запятую)", value="NVDA, PLTR, MSFT, SNOW, AAPL, AMD")
    portfolio_capital = st.number_input("Размер капитала портфеля ($)", min_value=1000, value=100000, step=5000)
    
    st.divider()
    st.subheader("🎛️ Калибровка 10Y DCF")

try:
    with st.spinner(f"Загружаем институциональную модель для {ticker}..."):
        data = fetch_company_data(ticker)
        
    hist_df = data["history"]
    if hist_df.empty:
        st.error("Не удалось выгрузить отчетность. Проверь тикер.")
        st.stop()

    with st.sidebar:
        wacc_input = st.slider("Ставка дисконтирования (WACC %)", 6.0, 15.0, round(data["wacc"] * 100, 1), 0.1) / 100.0
        default_growth = round(data["smart_growth_est"] * 100, 1)
        growth_input = st.slider("Прогноз роста FCF (1–5 год, %)", -10.0, 75.0, default_growth, 0.5) / 100.0
        term_input = st.slider("Терминальный рост (6–10+ год, %)", 2.0, 4.5, 3.5, 0.1) / 100.0
        st.caption(f"Исторический CAGR выручки: **{data['rev_cagr']*100:.1f}%**")
        st.caption(f"Smart-оценка импульса роста: **{data['smart_growth_est']*100:.1f}%**")
        st.caption(f"Безрисковая ставка 10Y US: **{data['rf']*100:.2f}%**")

    base_fcf = data["latest_true_fcf"] if use_true_fcf else data["latest_std_fcf"]
    fair_price = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input, growth_input, term_input)
    implied_growth = calculate_reverse_dcf(data["price"], base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input, term_input)
    upside = ((fair_price - data["price"]) / data["price"] * 100) if data["price"] > 0 else 0

    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 1. Оценка 10Y DCF & Качество Кэша",
        "🔥 2. Рентген & Стресс-Тест Портфеля",
        "🕵️‍♂️ 3. Радар Инсайдеров & Институционалов",
        "🧠 4. Форензик-Аудит 10-K & Инвест-Мемо"
    ])

    # ==================== ВКЛАДКА 1: ГЛУБОКИЙ РАЗБОР АКЦИИ ====================
    with tab1:
        st.subheader(f"{data['name']} ({ticker}) — {data['industry']}")
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Текущая цена", f"${data['price']:,.2f}", f"Target Уолл-стрит: ${data['target_mean_price']:,.0f}" if data['target_mean_price'] else None)
        c2.metric(f"Справедливая (10Y {'True' if use_true_fcf else 'Std'} DCF)", f"${fair_price:,.2f}" if base_fcf > 0 else "N/A", f"{upside:+.1f}% к рынку" if base_fcf > 0 else "Убыток FCF")
        c3.metric("Заложено в цену (Reverse DCF)", f"{implied_growth*100:.1f}% / год" if implied_growth is not None else "N/A", f"Прогноз модели: {growth_input*100:.1f}%", delta_color="off")
        c4.metric("Rule of 40 (Tech-индекс)", f"{data['rule_of_40']:.1f}%", "Лидер (>40%)" if data['rule_of_40'] >= 40 else "Ниже 40%", delta_color="normal" if data['rule_of_40'] >= 40 else "inverse")
        c5.metric("Altman Z-Score (Баланс)", f"{data['z_score']:.1f}", "Крепость (>3.0)" if data['z_score'] > 3 else "Норма/Риск")

        st.divider()
        left_col, right_col = st.columns([3, 2])

        with left_col:
            st.markdown("#### 🕵️‍♂️ Динамика денежных потоков: GAAP Net Income vs Standard FCF vs True FCF")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["Net Income"]/1e9, name="Net Income (Бумажная)", marker_color="#58a6ff"))
            fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["Standard FCF"]/1e9, name="Standard FCF", marker_color="#3fb950"))
            fig.add_trace(go.Bar(x=hist_df["Year"], y=hist_df["True FCF"]/1e9, name="True FCF (минус SBC)", marker_color="#d29922"))
            fig.update_layout(barmode="group", template="plotly_dark", yaxis_title="Миллиарды USD ($B)", height=360, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

        with right_col:
            st.markdown("#### 📊 Коридор справедливой цены (Bear / Base / Bull / Wall St)")
            if base_fcf > 0:
                bear_p = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], wacc_input + 0.015, growth_input * 0.75, term_input)
                bull_p = calculate_dcf(base_fcf, data["shares"], data["total_cash"], data["total_debt"], max(wacc_input - 0.01, 0.065), growth_input * 1.20, term_input)
                ws_target = data["target_mean_price"] or fair_price
                scen_fig = go.Figure(go.Bar(
                    x=["Bear (Пессимист)", "Рынок сейчас", "Твой 10Y DCF", "Target Уолл-стрит", "Bull (Оптимист)"],
                    y=[bear_p, data["price"], fair_price, ws_target, bull_p],
                    marker_color=["#f85149", "#8b949e", "#58a6ff", "#a371f7", "#3fb950"],
                    text=[f"${p:,.1f}" for p in [bear_p, data["price"], fair_price, ws_target, bull_p]],
                    textposition="auto"
                ))
                scen_fig.update_layout(template="plotly_dark", yaxis_title="Цена акции ($)", height=360, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(scen_fig, use_container_width=True)

        with st.expander("📂 Открыть полную финансовую таблицу (Выручка, R&D, Buybacks, SBC, Маржинальность)", expanded=True):
            display_df = hist_df.copy()
            for col in ["Revenue", "Net Income", "EBIT", "R&D", "Standard FCF", "SBC", "Buybacks", "True FCF"]:
                display_df[col] = display_df[col].apply(lambda x: f"${x/1e9:,.2f}B")
            for col in ["SBC % of Rev", "FCF Margin %", "True FCF Margin %"]:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}%")
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ==================== ВКЛАДКА 2: РЕНТГЕН & СТРЕСС-ТЕСТ ПОРТФЕЛЯ ====================
    with tab2:
        st.markdown("### 🔥 Рентген Портфеля & Макро Стресс-Тест")
        tickers = [t.strip().upper() for t in pool_input.split(",") if t.strip()]
        if tickers:
            with st.spinner("Сканируем все компании портфеля по 10-летней модели DCF..."):
                xray_df = analyze_portfolio_xray(tickers)
                
            if not xray_df.empty:
                total_sbc = xray_df["SBC ($B)"].sum()
                most_dilutive = xray_df.sort_values(by="SBC Eat of FCF (%)", ascending=False).iloc[0]
                best_value = xray_df.sort_values(by="Upside / Downside (%)", ascending=False).iloc[0]
                avg_beta = xray_df["Beta"].mean()
                weighted_upside = (xray_df["Upside / Downside (%)"] * (xray_df["Weight (%)"] / 100.0)).sum()
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Скрытый налог SBC в портфеле", f"${total_sbc:,.2f}B", "Размытие долей за год", delta_color="inverse")
                k2.metric("Главная ловушка SBC (Trap)", f"{most_dilutive['Ticker']}", f"Съедает {most_dilutive['SBC Eat of FCF (%)']}% от FCF", delta_color="inverse")
                k3.metric("Лидер по 10Y True DCF", f"{best_value['Ticker']}", f"{best_value['Upside / Downside (%)']:+.1f}% потенциал")
                k4.metric("Beta портфеля (Волатильность)", f"{avg_beta:.2f}", f"Суммарный DCF потенциал: {weighted_upside:+.1f}%")
                
                st.dataframe(xray_df, use_container_width=True, hide_index=True)
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("#### 🩸 Доля денежного потока (FCF), которую забирает менеджмент через SBC")
                    fig_sbc = go.Figure(go.Bar(
                        x=xray_df["Ticker"],
                        y=xray_df["SBC Eat of FCF (%)"],
                        marker_color=["#f85149" if v > 25 else "#3fb950" for v in xray_df["SBC Eat of FCF (%)"]],
                        text=xray_df["SBC Eat of FCF (%)"].apply(lambda x: f"{x:.1f}%"),
                        textposition="auto"
                    ))
                    fig_sbc.update_layout(template="plotly_dark", yaxis_title="% от Standard FCF", height=320)
                    st.plotly_chart(fig_sbc, use_container_width=True)
                    
                with col_b:
                    st.markdown("#### 🎈 Прогноз роста модели vs Ожидания толпы в текущей цене")
                    fig_gap = go.Figure()
                    fig_gap.add_trace(go.Bar(x=xray_df["Ticker"], y=xray_df["Smart Growth Est (%)"], name="Прогнозный импульс роста (%)", marker_color="#3fb950"))
                    fig_gap.add_trace(go.Bar(x=xray_df["Ticker"], y=xray_df["Implied Growth Needed (%)"], name="Заложено в цену (Reverse DCF %)", marker_color="#d29922"))
                    fig_gap.update_layout(barmode="group", template="plotly_dark", yaxis_title="Годовой рост (%)", height=320)
                    st.plotly_chart(fig_gap, use_container_width=True)

                st.divider()
                st.markdown("#### ⚡ Макроэкономический Стресс-Тест твоего капитала")
                sc1, sc2, sc3 = st.columns(3)
                rate_shock = portfolio_capital * (-0.08 * avg_beta)
                recession_shock = portfolio_capital * (-0.18 * avg_beta)
                ai_boom = portfolio_capital * (0.15 * avg_beta)
                sc1.metric("Шок ставки ФРС (+100 б.п. к WACC)", f"${portfolio_capital + rate_shock:,.0f}", f"{rate_shock/portfolio_capital*100:.1f}% ({rate_shock:+,.0f}$)")
                sc2.metric("Сжатие мультипликаторов (Tech Correction -20%)", f"${portfolio_capital + recession_shock:,.0f}", f"{recession_shock/portfolio_capital*100:.1f}% ({recession_shock:+,.0f}$)")
                sc3.metric("Продолжение AI-цикла (+15% S&P 500)", f"${portfolio_capital + ai_boom:,.0f}", f"+{ai_boom/portfolio_capital*100:.1f}% (+{ai_boom:,.0f}$)")

    # ==================== ВКЛАДКА 3: ИНСАЙДЕРЫ И ИНСТИТУЦИОНАЛЫ ====================
    with tab3:
        st.markdown(f"### 🕵️‍♂️ Структура владения и сделки инсайдеров (SEC Form 4): {ticker}")
        ic1, ic2, ic3 = st.columns(3)
        ic1.metric("Доля фондов (Institutions)", f"{(data['inst_ownership'] or 0)*100:.1f}%", "Уолл-стрит и ETF")
        ic2.metric("Доля инсайдеров (Founders & Execs)", f"{(data['insider_ownership'] or 0)*100:.2f}%", "Skin in the game")
        ic3.metric("Short Float (Ставки против акции)", f"{(data['short_ratio'] or 0)*100:.2f}%", "Риск шорт-сквиза" if (data['short_ratio'] or 0) > 0.1 else "Низкий интерес шортистов")
        
        ins_df = fetch_insider_activity(ticker)
        if not ins_df.empty:
            st.markdown("#### 📋 Последние зарегистрированные транзакции топ-менеджмента и директоров")
            st.dataframe(ins_df, use_container_width=True, hide_index=True)
        else:
            st.info("По данному тикеру нет недавних открытых транзакций Form 4 в публичном фиде.")

    # ==================== ВКЛАДКА 4: ФОРЕНЗИК-АУДИТ 10-K & МЕМОРАНДУМ ====================
    with tab4:
        st.markdown(f"### 🧠 Автоматический Форензик-Аудит отчетности 10-K/10-Q: {ticker}")
        score, flags, memo_md = generate_forensic_audit_and_memo(data, fair_price, implied_growth)
        
        st.progress(max(min(score, 100), 0) / 100.0, text=f"Институциональный рейтинг качества отчетности (Truth Score): {score}/100")
        for title, desc in flags:
            with st.container(border=True):
                st.markdown(f"**{title}** — {desc}")
                
        st.divider()
        st.markdown(memo_md)
        st.download_button(
            label="📥 Скачать готовый Investment Committee Memo (.md)",
            data=memo_md,
            file_name=f"{ticker}_Investment_Memo.md",
            mime="text/markdown"
        )

except Exception as e:
    st.error(f"Ошибка выполнения: {e}")
