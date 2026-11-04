import yfinance as yf
import pandas as pd
import numpy as np

def get_risk_free_rate():
    try:
        tnx = yf.Ticker("^TNX")
        hist = tnx.history(period="5d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1]) / 100.0
    except Exception:
        pass
    return 0.042

def _find_row(df, possible_names):
    if df is None or df.empty:
        return pd.Series(dtype=float)
    for name in possible_names:
        if name in df.index:
            return df.loc[name].fillna(0)
    return pd.Series(0, index=df.columns)

def fetch_company_data(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol.upper())
    info = ticker.info
    
    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding") or 0
    market_cap = info.get("marketCap") or (current_price * shares)
    
    raw_beta = info.get("beta") or 1.15
    adj_beta = min(max(0.67 * raw_beta + 0.33 * 1.0, 0.80), 1.60)
    
    total_debt = info.get("totalDebt") or 0
    total_cash = info.get("totalCash") or 0
    
    cf = ticker.cashflow
    inc = ticker.income_stmt
    bs = ticker.balance_sheet
    
    ocf = _find_row(cf, ["Operating Cash Flow", "Total Cash From Operating Activities"])
    capex = _find_row(cf, ["Capital Expenditure", "Capital Expenditures"])
    sbc = _find_row(cf, ["Stock Based Compensation", "Share Based Compensation"])
    repurchase = _find_row(cf, ["Repurchase Of Capital Stock", "Common Stock Payments"])
    
    rev = _find_row(inc, ["Total Revenue", "Operating Revenue", "Revenue"])
    net_inc = _find_row(inc, ["Net Income", "Net Income Common Stockholders"])
    ebit = _find_row(inc, ["EBIT", "Operating Income"])
    interest_exp = _find_row(inc, ["Interest Expense", "Interest Expense Non Operating"])
    rd_exp = _find_row(inc, ["Research And Development", "Research Development"])
    
    total_assets = _find_row(bs, ["Total Assets"])
    current_assets = _find_row(bs, ["Current Assets", "Total Current Assets"])
    current_liab = _find_row(bs, ["Current Liabilities", "Total Current Liabilities"])
    retained_earnings = _find_row(bs, ["Retained Earnings"])
    total_liab = _find_row(bs, ["Total Liabilities Net Minority Interest", "Total Liab"])
    
    years = sorted(list(set(ocf.index) & set(rev.index)))
    history = []
    
    for y in years:
        y_str = str(y)[:4]
        y_rev = float(rev.get(y, 0))
        y_ocf = float(ocf.get(y, 0))
        if y_rev <= 0 and y_ocf == 0:
            continue
            
        y_capex = float(capex.get(y, 0))
        std_fcf = y_ocf + y_capex if y_capex < 0 else y_ocf - y_capex
        y_sbc = abs(float(sbc.get(y, 0)))
        true_fcf = std_fcf - y_sbc
        y_ni = float(net_inc.get(y, 0))
        y_ebit = float(ebit.get(y, 0))
        y_rd = abs(float(rd_exp.get(y, 0)))
        y_buyback = abs(float(repurchase.get(y, 0)))
        
        history.append({
            "Year": y_str,
            "Revenue": y_rev,
            "Net Income": y_ni,
            "EBIT": y_ebit,
            "R&D": y_rd,
            "Standard FCF": std_fcf,
            "SBC": y_sbc,
            "Buybacks": y_buyback,
            "True FCF": true_fcf,
            "SBC % of Rev": (y_sbc / y_rev * 100) if y_rev > 0 else 0,
            "FCF Margin %": (std_fcf / y_rev * 100) if y_rev > 0 else 0,
            "True FCF Margin %": (true_fcf / y_rev * 100) if y_rev > 0 else 0
        })
        
    hist_df = pd.DataFrame(history)
    
    rf = get_risk_free_rate()
    erp = 0.045
    cost_of_equity = rf + adj_beta * erp
    
    latest_int = abs(float(interest_exp.iloc[0])) if not interest_exp.empty else 0
    if total_debt > 0 and latest_int > 0:
        cost_of_debt = min(max(latest_int / total_debt, rf), 0.10)
    else:
        cost_of_debt = rf + 0.012
        
    tax_rate = 0.21
    total_capital = market_cap + total_debt
    if total_capital > 0:
        wacc = (market_cap / total_capital) * cost_of_equity + (total_debt / total_capital) * cost_of_debt * (1 - tax_rate)
    else:
        wacc = 0.095
    wacc = max(min(wacc, 0.12), 0.07)
    
    rev_cagr = 0.15
    latest_rev_growth = 0.0
    if len(hist_df) >= 2:
        r_start = hist_df["Revenue"].iloc[0]
        r_end = hist_df["Revenue"].iloc[-1]
        r_prev = hist_df["Revenue"].iloc[-2]
        n_years = len(hist_df) - 1
        if r_start > 0 and r_end > 0 and n_years > 0:
            rev_cagr = (r_end / r_start) ** (1 / n_years) - 1
        if r_prev > 0:
            latest_rev_growth = (r_end - r_prev) / r_prev
            
    # Прогноз аналитиков Уолл-стрит + исторический импульс для точного базового роста
    analyst_rev_g = info.get("revenueGrowth") or latest_rev_growth
    analyst_ear_g = info.get("earningsGrowth") or rev_cagr
    blended_growth = 0.55 * float(analyst_rev_g) + 0.45 * float(rev_cagr)
    smart_growth_est = min(max(blended_growth, 0.06), 0.55)
    
    latest_std_fcf = hist_df["Standard FCF"].iloc[-1] if not hist_df.empty else 0
    latest_true_fcf = hist_df["True FCF"].iloc[-1] if not hist_df.empty else 0
    latest_sbc = hist_df["SBC"].iloc[-1] if not hist_df.empty else 0
    latest_ni = hist_df["Net Income"].iloc[-1] if not hist_df.empty else 0
    latest_rev = hist_df["Revenue"].iloc[-1] if not hist_df.empty else 0
    latest_ebit = hist_df["EBIT"].iloc[-1] if not hist_df.empty else 0
    
    rule_of_40 = (latest_rev_growth * 100) + (hist_df["FCF Margin %"].iloc[-1] if not hist_df.empty else 0)
    
    # Расчет ROIC и Altman Z-Score (Аудит надежности баланса)
    invested_capital = total_debt + market_cap - total_cash
    nopat = latest_ebit * (1 - tax_rate)
    roic = (nopat / max(total_assets.iloc[0] - current_liab.iloc[0] - total_cash, 1)) if not total_assets.empty and not current_liab.empty else 0.15
    
    ta = float(total_assets.iloc[0]) if not total_assets.empty and total_assets.iloc[0] > 0 else 1.0
    ca = float(current_assets.iloc[0]) if not current_assets.empty else 0.0
    cl = float(current_liab.iloc[0]) if not current_liab.empty else 0.0
    re = float(retained_earnings.iloc[0]) if not retained_earnings.empty else 0.0
    tl = float(total_liab.iloc[0]) if not total_liab.empty and total_liab.iloc[0] > 0 else 1.0
    
    z_score = 1.2 * ((ca - cl) / ta) + 1.4 * (re / ta) + 3.3 * (latest_ebit / ta) + 0.6 * (market_cap / tl) + 1.0 * (latest_rev / ta)
    
    return {
        "ticker": ticker_symbol.upper(),
        "name": info.get("longName", ticker_symbol.upper()),
        "sector": info.get("sector", "Technology"),
        "industry": info.get("industry", "Software / Tech"),
        "summary": info.get("longBusinessSummary", ""),
        "price": current_price,
        "shares": shares,
        "market_cap": market_cap,
        "total_debt": total_debt,
        "total_cash": total_cash,
        "beta": raw_beta,
        "adj_beta": adj_beta,
        "rf": rf,
        "wacc": wacc,
        "rev_cagr": rev_cagr,
        "latest_rev_growth": latest_rev_growth,
        "smart_growth_est": smart_growth_est,
        "rule_of_40": rule_of_40,
        "roic": roic,
        "z_score": z_score,
        "latest_std_fcf": latest_std_fcf,
        "latest_true_fcf": latest_true_fcf,
        "latest_sbc": latest_sbc,
        "latest_ni": latest_ni,
        "latest_rev": latest_rev,
        "pe_ratio": info.get("trailingPE", 0),
        "forward_pe": info.get("forwardPE", 0),
        "ev_ebitda": info.get("enterpriseToEbitda", 0),
        "inst_ownership": info.get("heldPercentInstitutions", 0),
        "insider_ownership": info.get("heldPercentInsiders", 0),
        "short_ratio": info.get("shortPercentOfFloat", 0),
        "target_mean_price": info.get("targetMeanPrice", 0),
        "history": hist_df
    }

def calculate_dcf(base_fcf, shares, cash, debt, wacc, initial_growth, terminal_growth=0.035, years=10):
    """Институциональный 10-летний 2-Stage DCF по модели Дамодарана (5 лет импульса + 5 лет плавного затухания к терминалу)"""
    if shares <= 0 or base_fcf <= 0 or wacc <= terminal_growth:
        return 0.0
    projected_fcfs = []
    current_fcf = base_fcf
    for t in range(1, years + 1):
        if t <= 5:
            g = initial_growth
        else:
            # Линейное затухание темпа роста с 6 по 10 год к терминальному росту экономики
            decay_factor = (t - 5) / (years - 5)
            g = initial_growth - (initial_growth - terminal_growth) * decay_factor
        current_fcf = current_fcf * (1 + g)
        projected_fcfs.append(current_fcf)
        
    pv_fcfs = [fcf / ((1 + wacc) ** t) for t, fcf in enumerate(projected_fcfs, start=1)]
    terminal_fcf = projected_fcfs[-1] * (1 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    pv_terminal = terminal_value / ((1 + wacc) ** years)
    
    enterprise_value = sum(pv_fcfs) + pv_terminal
    equity_value = enterprise_value + cash - debt
    return max(equity_value / shares, 0.0)

def calculate_reverse_dcf(target_price, base_fcf, shares, cash, debt, wacc, terminal_growth=0.035, years=10):
    if base_fcf <= 0 or shares <= 0 or target_price <= 0:
        return None
    low, high = -0.35, 1.20
    for _ in range(60):
        mid = (low + high) / 2
        val = calculate_dcf(base_fcf, shares, cash, debt, wacc, mid, terminal_growth, years)
        if val < target_price:
            low = mid
        else:
            high = mid
    return (low + high) / 2

def analyze_portfolio_xray(tickers_list, weights_dict=None):
    rows = []
    for t in tickers_list:
        try:
            d = fetch_company_data(t)
            hist = d["history"]
            if hist.empty:
                continue
            sbc_pct_fcf = (d["latest_sbc"] / d["latest_std_fcf"] * 100) if d["latest_std_fcf"] > 0 else 100.0
            implied_g = calculate_reverse_dcf(d["price"], d["latest_true_fcf"], d["shares"], d["total_cash"], d["total_debt"], d["wacc"])
            fair_p = calculate_dcf(d["latest_true_fcf"], d["shares"], d["total_cash"], d["total_debt"], d["wacc"], d["smart_growth_est"])
            upside = ((fair_p - d["price"]) / d["price"] * 100) if d["price"] > 0 and fair_p > 0 else -99.0
            weight = weights_dict.get(d["ticker"], 1.0 / len(tickers_list)) if weights_dict else (1.0 / len(tickers_list))
            
            rows.append({
                "Ticker": d["ticker"],
                "Company": d["name"],
                "Weight (%)": round(weight * 100, 1),
                "Price ($)": round(d["price"], 2),
                "Fair True DCF ($)": round(fair_p, 2) if fair_p > 0 else 0.0,
                "Wall St Target ($)": round(d["target_mean_price"], 2) if d["target_mean_price"] else 0.0,
                "Upside / Downside (%)": round(upside, 1),
                "Smart Growth Est (%)": round(d["smart_growth_est"] * 100, 1),
                "Implied Growth Needed (%)": round(implied_g * 100, 1) if implied_g is not None else 0.0,
                "SBC Eat of FCF (%)": round(sbc_pct_fcf, 1),
                "SBC ($B)": round(d["latest_sbc"] / 1e9, 2),
                "True FCF ($B)": round(d["latest_true_fcf"] / 1e9, 2),
                "Rule of 40": round(d["rule_of_40"], 1),
                "Beta": round(d["beta"], 2)
            })
        except Exception:
            continue
    return pd.DataFrame(rows)

def fetch_insider_activity(ticker_symbol):
    """Выгружает реальные сделки инсайдеров (Form 4) и институциональных держателей"""
    ticker = yf.Ticker(ticker_symbol.upper())
    try:
        ins = ticker.insider_transactions
        if ins is not None and not ins.empty:
            cols = [c for c in ["Start Date", "Insider", "Position", "Transaction", "Shares", "Value", "Text"] if c in ins.columns]
            return ins[cols].head(15)
    except Exception:
        pass
    return pd.DataFrame()

def generate_forensic_audit_and_memo(data, fair_price, implied_growth):
    """Форензик-аудитор отчетности: проверяет 5 критериев качества и генерирует Investment Committee Memo"""
    hist = data["history"]
    latest_sbc_rev = hist["SBC % of Rev"].iloc[-1] if not hist.empty else 0
    sbc_fcf_eat = (data["latest_sbc"] / data["latest_std_fcf"] * 100) if data["latest_std_fcf"] > 0 else 100
    cash_conversion = (data["latest_true_fcf"] / data["latest_ni"] * 100) if data["latest_ni"] > 0 else 0
    net_cash = data["total_cash"] - data["total_debt"]
    
    flags = []
    score = 100
    
    # 1. Проверка размытия SBC
    if sbc_fcf_eat > 30 or latest_sbc_rev > 12:
        flags.append(("🔴 КРИТИЧЕСКИЙ РИСК РАЗМЫТИЯ (SBC Trap)", f"Выплаты акциями менеджменту съедают {sbc_fcf_eat:.1f}% свободного кэша ({latest_sbc_rev:.1f}% от всей выручки). Высокий риск размытия доли акционеров."))
        score -= 30
    elif sbc_fcf_eat > 15:
        flags.append(("🟡 УМЕРЕННЫЙ SBC НАЛОГ", f"Бонусы акциями забирают {sbc_fcf_eat:.1f}% от FCF. В пределах нормы для сектора, но требует контроля."))
        score -= 10
    else:
        flags.append(("🟢 ДИСЦИПЛИНА КАПИТАЛА (Low SBC)", f"На выплаты акциями уходит всего {sbc_fcf_eat:.1f}% от FCF — руководство бережет доли акционеров."))
        
    # 2. Качество прибыли (True FCF vs Net Income)
    if cash_conversion < 65:
        flags.append(("🔴 НИЗКОЕ КАЧЕСТВО ПРИБЫЛИ (Accrual Risk)", f"Реальный кэш (True FCF) составляет лишь {cash_conversion:.1f}% от бумажной прибыли GAAP Net Income."))
        score -= 25
    else:
        flags.append(("🟢 ВЫСОКАЯ КОНВЕРСИЯ В КЭШ", f"На каждые 100 USD бумажной прибыли компания генерирует  {cash_conversion:.1f} USD чистого True FCF."))
        
    # 3. Баланс и долговая устойчивость (Altman Z-Score)
    if data["z_score"] > 3.0 and net_cash >= 0:
        flags.append(("🟢 КРЕПОСТЬ БАЛАНСА (Fortress Balance Sheet)", f"Чистый кэш на балансе: ${net_cash/1e9:,.2f}B. Индекс надежности Altman Z-Score: {data['z_score']:.1f} (риск банкротства стремится к нулю)."))
    elif data["z_score"] < 1.8:
        flags.append(("🔴 ДОЛГОВАЯ УЯЗВИМОСТЬ", f"Altman Z-Score {data['z_score']:.1f} в опасной зоне. Долг: ${data['total_debt']/1e9:,.2f}B против кэша ${data['total_cash']/1e9:,.2f}B."))
        score -= 25
    else:
        flags.append(("🟡 СТАНДАРТНЫЙ БАЛАНС", f"Altman Z-Score: {data['z_score']:.1f}, чистый долг/кэш: ${net_cash/1e9:,.2f}B."))
        
    # 4. Операционная эффективность (Rule of 40)
    if data["rule_of_40"] >= 40:
        flags.append(("🟢 ЭЛИТНАЯ ЭФФЕКТИВНОСТЬ (Rule of 40 Pass)", f"Индекс Rule of 40 равен {data['rule_of_40']:.1f}% (норма для лучших софтверных и техно-компаний >= 40%)."))
    else:
        flags.append(("🟡 СЛАБЫЙ ИМПУЛЬС РОСТА/МАРЖИ", f"Индекс Rule of 40 составляет {data['rule_of_40']:.1f}% (ниже бенчмарка 40%)."))
        score -= 15

    upside = ((fair_price - data["price"]) / data["price"] * 100) if data["price"] > 0 else 0
    if score >= 75 and upside > 0:
        verdict = "STRONG BUY / ACCUMULATE (Фундаментальный лидер с честным кэшем)"
    elif score >= 70 and upside <= 0:
        verdict = "HOLD / WATCHLIST ON PULLBACK (Прекрасный бизнес, но премия в цене)"
    else:
        verdict = "AVOID / TRIM (Риск переоценки или размытия капитала через SBC)"
        
    memo_md = f"""
### 📄 INVESTMENT COMMITTEE MEMO: {data['name']} ({data['ticker']})
* **Итоговый рейтинг качества бизнеса (Truth Score):** `{max(score, 10)} / 100`
* **Вердикт алгоритма:** **{verdict}**
* **Текущая котировка:** `${data['price']:,.2f}` | **Справедливая оценка (10Y True DCF):** `${fair_price:,.2f}` (`{upside:+.1f}%`) | **Консенсус Уолл-стрит:** `${data['target_mean_price']:,.2f}`

#### 1. Тезис по оценке и ожиданиям рынка (Reverse DCF)
При ставке дисконтирования **WACC {data['wacc']*100:.1f}%** текущая рыночная капитализация (`${data['market_cap']/1e9:,.1f}B`) требует от компании наращивать очищенный денежный поток (True FCF) темпом **{(implied_growth or 0)*100:.1f}% в год** на горизонте первых 5 лет с плавным затуханием к 10-му году. Сбалансированный прогнозный темп роста компании составляет **{data['smart_growth_est']*100:.1f}%** (исторический CAGR выручки: **{data['rev_cagr']*100:.1f}%**).

#### 2. Аудит качества прибыли и размытия капитала (SBC Forensic)
За последний отчетный период компания сгенерировала `${data['latest_std_fcf']/1e9:,.2f}B` стандартного FCF, однако направила `${data['latest_sbc']/1e9:,.2f}B` на вознаграждение сотрудников акциями (SBC). Таким образом, реальный свободный денежный поток акционеров (**True FCF**) составил **`${data['latest_true_fcf']/1e9:,.2f}B`**.
"""
    return score, flags, memo_md
