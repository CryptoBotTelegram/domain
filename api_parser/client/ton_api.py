# ton_api.py
from requests import request
import os
from dotenv import load_dotenv

load_dotenv()

TONAPI_KEY = os.getenv('TONAPI_KEY', '')

def TON_jettons(limit: int = 100, offset: int = 0) -> list:
    headers = {'Authorization': f'Bearer {TONAPI_KEY}'} if TONAPI_KEY else {}
    response = request(
        url=f"https://tonapi.io/v2/jettons?limit={limit}&offset={offset}",
        method="GET",
        headers=headers
    )
    return response.json().get('jettons', [])

def TON_jetton_details(address: str) -> dict:
    headers = {'Authorization': f'Bearer {TONAPI_KEY}'} if TONAPI_KEY else {}
    response = request(
        url=f"https://tonapi.io/v2/jettons/{address}",
        method="GET",
        headers=headers
    )
    return response.json()

def TON_jetton_holders(address: str, limit: int = 100, offset: int = 0) -> dict:
    headers = {'Authorization': f'Bearer {TONAPI_KEY}'} if TONAPI_KEY else {}
    response = request(
        url=f"https://tonapi.io/v2/jettons/{address}/holders?limit={limit}&offset={offset}",
        method="GET",
        headers=headers
    )
    return response.json()

def TON_jetton_events(address: str, limit: int = 100, start_date: str = None) -> dict:
    headers = {'Authorization': f'Bearer {TONAPI_KEY}'} if TONAPI_KEY else {}
    url = f"https://tonapi.io/v2/jettons/{address}/events?limit={limit}"
    if start_date:
        url += f"&start_date={start_date}"
    response = request(url=url, method="GET", headers=headers)
    return response.json()