import aiohttp


async def fetch_usd_uah_rate_nbu() -> float | None:
    """
    External API: NBU public exchange rates (no API key required).
    Returns USD->UAH rate or None on error.
    """
    url = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
    except Exception:
        return None

    # Example element: { "r030":840, "txt":"Долар США", "rate":41.23, "cc":"USD", ... }
    for item in data:
        if str(item.get("cc", "")).upper() == "USD":
            try:
                return float(item["rate"])
            except Exception:
                return None
    return None

