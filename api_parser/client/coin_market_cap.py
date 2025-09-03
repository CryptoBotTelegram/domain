# coin_market_cap.py
from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json
from os import getenv


def CMC_listings_latest(limit: int = 50) -> dict:
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    parameters = {
        'start': '1',
        'limit': str(limit),
        'convert': 'USD'
    }
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': getenv('CMC_API_KEY', ''),
    }

    session = Session()
    session.headers.update(headers)

    try:
        response = session.get(url, params=parameters)
        data = json.loads(response.text)
        return {
            'datetime': data.get('status', {}).get('timestamp'),
            'data': data.get('data', []),
            'type': 'cmc_listings'
        }
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(f"CMC API Error: {e}")
        return {}


def CMC_market_pairs(symbol: str, limit: int = 50) -> dict:
    url = 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/market-pairs/latest'
    parameters = {
        'symbol': symbol,
        'limit': str(limit),
        'convert': 'USD'
    }
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': getenv('CMC_API_KEY', ''),
    }

    session = Session()
    session.headers.update(headers)

    try:
        response = session.get(url, params=parameters)
        data = json.loads(response.text)
        return {
            'datetime': data.get('status', {}).get('timestamp'),
            'data': data.get('data', {}),
            'type': 'cmc_market_pairs'
        }
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(f"CMC Market Pairs API Error: {e}")
        return {}