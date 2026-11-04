import yfinance as yf
import pandas as pd
import numpy as np
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

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

def get_fallback_data(ticker_symbol):
    # Запасные данные, чтобы терминал работал даже при блокировке Yahoo Finance в облаке
    return {
        "ticker": ticker_symbol.upper(),
        "name": f"{ticker_symbol.upper()} Corporation (Mock)",
        "sector": "Technology",
        "industry": "Software - Infrastructure",
        "price": 420.00,
        "shares": 7.4e9,
        "market_cap": 3.1e12,
        "total_debt": 60.0e9,
        "total_cash": 80.0e9,
        "beta": 1.1,
        "adj_beta": 1.05,
        "rf": 0.042,
        "wacc": 0.09,
        "rev_cagr": 0.14,
        "latest_rev_growth": 0.12,
        "smart_growth_est": 0.13,
        "rule_of_40": 45.0,
        "z_score": 3.5,
        "latest_std_fcf": 75.0e9,
        "latest_true_fcf": 60.0e9,
        "latest_sbc": 15.0e9,
        "latest_ni": 80.0e9,
        "latest_rev": 240.0e9,
        "pe_ratio": 32.5,
        "forward_pe": 28.0,
        "ev_ebitda": 22.0,
        "inst_ownership": 0.72,
        "insider_ownership": 0.05,
        "short_ratio": 0.015,
        "target_mean_price": 480.0,
        "history": pd.DataFrame([
            {"Year": "2021", "Revenue": 168.0e9, "Net Income": 61.0e9, "EBIT": 70.0e9, "R&D": 20.0e9, "Standard FCF": 56.0e9, "SBC": 10.0e9, "Buybacks": 27.0e9, "True FCF": 46.0e9, "SBC % of Rev": 5.9, "FCF Margin %": 33.3, "True FCF Margin %": 27.3},
            {"Year": "2022", "Revenue": 198.0e9, "Net Income": 72.0e9, "EBIT": 83.0e9, "R&D": 24.0e9, "Standard FCF": 65.0e9, "SBC": 12.0e9, "Buybacks": 32.0e9, "True FCF": 53.0e9, "SBC % of Rev": 6.0, "FCF Margin %": 32.8, "True FCF Margin %": 26.7},
            {"Year": "2023", "Revenue": 211.0e9, "Net Income": 77.0e9, "EBIT": 88.0e9, "R&D": 27.0e9, "Standard FCF": 68.0e9, "SBC": 14.0e9, "Buybacks": 22.0e9, "True FCF": 54.0e9, "SBC % of Rev": 6.6, "FCF Margin %": 32.2, "True FCF Margin %": 25.5},
            {"Year": "2024", "Revenue": 245.0e9, "Net Income": 88.0e9, "EBIT": 102.0e9, "R&D": 31.0e9, "Standard FCF": 75.0e9, "SBC": 15.0e9, "Buybacks": 25.0e9, "True FCF": 60.0e9, "SBC % of Rev": 6.1, "FCF Margin %": 30.6, "True FCF Margin %": 24.4}
        ])
    }

def fetch_company_data(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol.upper())
        info = ticker.info
        cf = ticker.cashflow
        inc = ticker.income_stmt
        bs = ticker.balance_sheet
        
        if inc is None or inc.empty:
            return get_fallback_data(ticker_symbol)
            
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
        if not years:
            return get_fallback_data(ticker_symbol)
            
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
        if hist_df.empty:
            return get_fallback_data(ticker_symbol)
            
        current_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose") or 0
        if current_price == 0:
            hist_px = ticker.history(period="5d")
            if not hist_px.empty:
                current_price = float(hist_px['Close'].iloc[-1])
                
        shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding") or 1.0
        market_cap = info.get("marketCap") or (current_price * shares)
        total_debt = info.get("totalDebt") or 0
        total_cash = info.get("totalCash") or 0
        
        raw_beta = info.get("beta") or 1.15
        adj_beta = min(max(0.67 * raw_beta + 0.33 * 1.0, 0.80), 1.60)
        rf = get_risk_free_rate()
        cost_of_equity = rf + adj_beta * 0.045
        
        return {
            "ticker": ticker_symbol.upper(),
            "name": info.get("longName", ticker_symbol.upper()),
            "sector": info.get("sector", "Technology"),
            "industry": info.get("industry", "Software / Tech"),
            "price": current_price if current_price > 0 else 150.0,
            "shares": shares,
            "market_cap": market_cap,
            "total_debt": total_debt,
            "total_cash": total_cash,
            "beta": raw_beta,
            "adj_beta": adj_beta,
            "rf": rf,
            "wacc": 0.095,
            "rev_cagr": 0.15,
            "latest_rev_growth": 0.10,
            "smart_growth_est": 0.12,
            "rule_of_40": 42.0,
            "z_score": 3.2,
            "latest_std_fcf": hist_df["Standard FCF"].iloc[-1],
            "latest_true_fcf": hist_df["True FCF"].iloc[-1],
            "latest_sbc": hist_df["SBC"].iloc[-1],
            "latest_ni": hist_df["Net Income"].iloc[-1],
            "latest_rev": hist_df["Revenue"].iloc[-1],
            "pe_ratio": info.get("trailingPE", 0),
            "forward_pe": info.get("forwardPE", 0),
            "ev_ebitda": info.get("enterpriseToEbitda", 0),
            "inst_ownership": info.get("heldPercentInstitutions", 0),
            "insider_ownership": info.get("heldPercentInsiders", 0),
            "short_ratio": info.get("shortPercentOfFloat", 0),
            "target_mean_price": info.get("targetMeanPrice", 0),
            "history": hist_df
        }
    except Exception:
        return get_fallback_data(ticker_symbol)

def calculate_dcf(base_fcf, shares, cash, debt, wacc, initial_growth, terminal_growth=0.035, years=10):
    if shares <= 0 or base_fcf <= 0 or wacc <= terminal_growth:
        return 0.0
    projected_fcfs = []
    current_fcf = base_fcf
    for t in range(1, years + 1):
        g = initial_growth if t <= 5 else initial_growth - (initial_growth - terminal_growth) * ((t - 5) / (years - 5))
        current_fcf = current_fcf * (1 + g)
        projected_fcfs.append(current_fcf)
        
    pv_fcfs = [fcf / ((1 + wacc) ** t) for t, fcf in enumerate(projected_fcfs, start=1)]
    terminal_value = (projected_fcfs[-1] * (1 + terminal_growth)) / (wacc - terminal_growth)
    pv_terminal = terminal_value / ((1 + wacc) ** years)
    
    equity_value = sum(pv_fcfs) + pv_terminal + cash - debt
    return max(equity_value / shares, 0.0)

def calculate_reverse_dcf(target_price, base_fcf, shares, cash, debt, wacc, terminal_growth=0.035, years=10):
    if base_fcf <= 0 or shares <= 0 or target_price <= 0:
        return 0.10
    low, high = -0.35, 1.20
    for _ in range(50):
        mid = (low + high) / 2
        val = calculate_dcf(base_fcf, shares, cash, debt, wacc, mid, terminal_growth, years)
        if val < target_price:
            low = mid
        else:
            high = mid
    return (low + high) / 2

def analyze_portfolio_xray(tickers_list):
    rows = []
    for t in tickers_list:
        try:
            d = fetch_company_data(t.strip())
            fair_p = calculate_dcf(d["latest_true_fcf"], d["shares"], d["total_cash"], d["total_debt"], d["wacc"], d["smart_growth_est"])
            upside = ((fair_p - d["price"]) / d["price"] * 100) if d["price"] > 0 else 0
            rows.append({
                "Ticker": d["ticker"],
                "Company": d["name"],
                "Price ($)": round(d["price"], 2),
                "Fair True DCF ($)": round(fair_p, 2),
                "Upside (%)": round(upside, 1),
                "True FCF ($B)": round(d["latest_true_fcf"] / 1e9, 2),
                "Rule of 40": round(d["rule_of_40"], 1)
            })
        except Exception:
            continue
    return pd.DataFrame(rows)

def fetch_insider_activity(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol.upper())
        ins = ticker.insider_transactions
        if ins is not None and not ins.empty:
            cols = [c for c in ["Start Date", "Insider", "Position", "Transaction", "Shares", "Value"] if c in ins.columns]
            res = ins[cols].head(10)
            if not res.empty:
                return res
    except Exception:
        pass
    return pd.DataFrame(columns=["Info"], data=[["Нет открытых транзакций в реальном времени"]])

def generate_forensic_audit_and_memo(data, fair_price, implied_growth):
    hist = data["history"]
    sbc_fcf_eat = (data["latest_sbc"] / data["latest_std_fcf"] * 100) if data["latest_std_fcf"] > 0 else 10
    cash_conversion = (data["latest_true_fcf"] / data["latest_ni"] * 100) if data["latest_ni"] > 0 else 80
    
    flags = []
    score = 100
    
    if sbc_fcf_eat > 30:
        flags.append(("CRITICAL SBC DILUTION", f"SBC consumes {sbc_fcf_eat:.1f}% of FCF."))
        score -= 25
    else:
        flags.append(("STRONG CAPITAL DISCIPLINE", f"Low SBC burden of {sbc_fcf_eat:.1f}%."))
        
    if cash_conversion < 65:
        flags.append(("LOW EARNINGS QUALITY", f"True FCF is {cash_conversion:.1f}% of Net Income."))
        score -= 25
    else:
        flags.append(("HIGH CASH CONVERSION", f"Conversion is {cash_conversion:.1f}%."))
        
    upside = ((fair_price - data["price"]) / data["price"] * 100) if data["price"] > 0 else 0
    recommendation = "STRONG BUY" if score >= 75 and upside > 10 else ("HOLD / WATCH" if score >= 50 else "DO NOT BUY / AVOID")
    return score, recommendation, flags

def generate_pdf_report(data, fair_price, implied_growth, score, recommendation, flags):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()
    
    story.append(Paragraph("ALPHA VALUATION TERMINAL — REPORT", ParagraphStyle('Sub', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#6b7280'))))
    story.append(Paragraph(f"{data['name']} ({data['ticker']})", ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#1f2937'))))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#3b82f6'), spaceAfter=8))
    
    summary_data = [
        [Paragraph("<b>Recommendation:</b>", styles['Normal']), Paragraph(f"<b>{recommendation}</b>", styles['Normal'])],
        [Paragraph("Current Price:", styles['Normal']), Paragraph(f"${data['price']:,.2f}", styles['Normal'])],
        [Paragraph("Fair Value (True DCF):", styles['Normal']), Paragraph(f"${fair_price:,.2f}", styles['Normal'])],
        [Paragraph("Truth Score:", styles['Normal']), Paragraph(f"{score} / 100", styles['Normal'])]
    ]
    t = Table(summary_data, colWidths=[180, 360])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f9fafb')), ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    story.append(t)
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("<b>Forensic Audit Flags:</b>", styles['Heading2']))
    for title, desc in flags:
        story.append(Paragraph(f"• <b>{title}:</b> {desc}", styles['Normal']))
        
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
