_FAKE = {
    "AAPL": {"price": 231.4, "pe": 35.2, "market_cap_b": 3510, "rev_growth_yoy": 0.06},
    "MSFT": {"price": 468.1, "pe": 37.9, "market_cap_b": 3480, "rev_growth_yoy": 0.15},
}


def lookup_market_data(ticker: str) -> str:
    t = ticker.strip().upper()
    d = _FAKE.get(t) or {"price": 100.0, "pe": 20.0, "market_cap_b": 250, "rev_growth_yoy": 0.08}
    return (
        f"{t}: price=${d['price']}, P/E={d['pe']}, "
        f"market cap=${d['market_cap_b']}B, revenue growth YoY={d['rev_growth_yoy']:.0%}"
    )
