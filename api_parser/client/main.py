# main.py
import asyncio
import time
import json
import logging
import redis.asyncio as redis
from typing import Dict, Any, List
from datetime import datetime, timedelta
from ton_api import TON_jettons, TON_jetton_details, TON_jetton_holders, TON_jetton_events
from coin_market_cap import CMC_listings_latest, CMC_market_pairs
from os import getenv
from dotenv import load_dotenv
import aiohttp

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data_collector.log')
    ]
)
logger = logging.getLogger(__name__)

# Redis подключение
redis_client = redis.Redis(
    host=getenv('REDIS_HOST', 'localhost'),
    port=int(getenv('REDIS_PORT', 6379)),
    db=int(getenv('REDIS_DB', 0)),
    password=getenv('REDIS_PASSWORD', None),
    decode_responses=True
)

# Конфигурация сбора данных
DATA_SOURCES = {
    'ton_jettons': {'interval': 1800, 'last_run': 0},  # 30 минут
    'ton_jetton_details': {'interval': 3600, 'last_run': 0},  # 1 час
    'ton_jetton_holders': {'interval': 7200, 'last_run': 0},  # 2 часа
    'ton_jetton_events': {'interval': 900, 'last_run': 0},  # 15 минут
    'cmc_listings': {'interval': 300, 'last_run': 0},  # 5 минут
    'cmc_market_pairs': {'interval': 600, 'last_run': 0},  # 10 минут
}

# Приоритетные jettons для детального отслеживания
PRIORITY_JETTONS = [
    "0:30025269501c8ec20ae637a8244aa2d98a41457ef3ecb6c04e200aead7baeed6",
    # Добавьте другие приоритетные jettons
]

# Глобальная HTTP-сессия для повторного использования
http_session = None


async def get_http_session():
    global http_session
    if http_session is None:
        http_session = aiohttp.ClientSession()
    return http_session


async def close_http_session():
    global http_session
    if http_session:
        await http_session.close()
        http_session = None


async def collect_ton_jettons(limit: int = 50) -> Dict[str, Any]:
    """Сбор данных о jettons из TON API"""
    try:
        session = await get_http_session()
        jettons = await asyncio.get_event_loop().run_in_executor(
            None, TON_jettons, limit
        )
        logger.info(f"TON jettons collected: {len(jettons)} items")

        # Анализ: находим jettons с быстрым ростом
        trending_jettons = []
        for jetton in jettons:
            holders_count = jetton.get('holders_count', 0)
            if holders_count > 100 and jetton.get('verification') != 'blacklist':
                trending_jettons.append({
                    'address': jetton['metadata']['address'],
                    'name': jetton['metadata']['name'],
                    'symbol': jetton['metadata']['symbol'],
                    'holders_count': holders_count,
                    'supply': jetton.get('total_supply', '0')
                })

        return {
            "source": "ton_jettons",
            "data": jettons,
            "analysis": {"trending": trending_jettons[:5]},
            "error": None
        }
    except Exception as e:
        error_msg = f"TON Jettons API error: {e}"
        logger.error(error_msg)
        return {"source": "ton_jettons", "data": None, "error": error_msg}


async def collect_ton_jetton_details(address: str) -> Dict[str, Any]:
    """Сбор детальной информации о конкретном jetton"""
    try:
        session = await get_http_session()
        details = await asyncio.get_event_loop().run_in_executor(
            None, TON_jetton_details, address
        )
        logger.info(f"TON jetton details collected for {address}")

        # Анализ: проверяем основные метрики
        analysis = {
            'is_scam': details.get('admin', {}).get('is_scam', False),
            'mintable': details.get('mintable', False),
            'supply': details.get('total_supply', '0'),
            'verification': details.get('verification', 'none')
        }

        return {
            "source": "ton_jetton_details",
            "address": address,
            "data": details,
            "analysis": analysis,
            "error": None
        }
    except Exception as e:
        error_msg = f"TON Jetton Details API error for {address}: {e}"
        logger.error(error_msg)
        return {"source": "ton_jetton_details", "address": address, "data": None, "error": error_msg}


async def collect_ton_jetton_holders(address: str) -> Dict[str, Any]:
    """Сбор информации о холдерах jetton"""
    try:
        session = await get_http_session()
        holders = await asyncio.get_event_loop().run_in_executor(
            None, TON_jetton_holders, address, 20
        )
        logger.info(f"TON jetton holders collected for {address}")

        # Анализ: концентрация средств
        total_holders = holders.get('total', 0)
        addresses = holders.get('addresses', [])

        if addresses:
            top_holder = addresses[0]
            concentration = float(top_holder.get('balance', 0)) / float(holders.get('total_supply', 1))
            analysis = {
                'total_holders': total_holders,
                'top_holder_balance': top_holder.get('balance', '0'),
                'concentration': concentration,
                'is_risky': concentration > 0.4  # Если топ-холдер владеет >40%
            }
        else:
            analysis = {'total_holders': total_holders}

        return {
            "source": "ton_jetton_holders",
            "address": address,
            "data": holders,
            "analysis": analysis,
            "error": None
        }
    except Exception as e:
        error_msg = f"TON Jetton Holders API error for {address}: {e}"
        logger.error(error_msg)
        return {"source": "ton_jetton_holders", "address": address, "data": None, "error": error_msg}


async def collect_ton_jetton_events(address: str) -> Dict[str, Any]:
    """Сбор событий по jetton"""
    try:
        session = await get_http_session()
        # Получаем события за последние 24 часа
        start_date = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
        events = await asyncio.get_event_loop().run_in_executor(
            None, TON_jetton_events, address, 50, start_date
        )
        logger.info(f"TON jetton events collected for {address}")

        # Анализ: активность транзакций
        events_list = events.get('events', [])
        analysis = {
            'event_count': len(events_list),
            'recent_activity': len(events_list) > 10  # Высокая активность
        }

        return {
            "source": "ton_jetton_events",
            "address": address,
            "data": events,
            "analysis": analysis,
            "error": None
        }
    except Exception as e:
        error_msg = f"TON Jetton Events API error for {address}: {e}"
        logger.error(error_msg)
        return {"source": "ton_jetton_events", "address": address, "data": None, "error": error_msg}


async def collect_cmc_listings() -> Dict[str, Any]:
    """Сбор данных из CoinMarketCap Listings"""
    try:
        session = await get_http_session()
        cmc_data = await asyncio.get_event_loop().run_in_executor(
            None, CMC_listings_latest, 30
        )
        logger.info("CMC listings data collected")

        # Анализ: находим самые volatile токены
        volatile_coins = []
        for coin in cmc_data.get('data', []):
            quote = coin.get('quote', {}).get('USD', {})
            change_24h = quote.get('percent_change_24h', 0)
            if abs(change_24h) > 10:  # >10% изменения за 24ч
                volatile_coins.append({
                    'name': coin.get('name'),
                    'symbol': coin.get('symbol'),
                    'change_24h': change_24h,
                    'price': quote.get('price')
                })

        return {
            "source": "cmc_listings",
            "data": cmc_data,
            "analysis": {"volatile": volatile_coins},
            "error": None
        }
    except Exception as e:
        error_msg = f"CMC API error: {e}"
        logger.error(error_msg)
        return {"source": "cmc_listings", "data": None, "error": error_msg}


async def collect_cmc_market_pairs(symbol: str = 'TON') -> Dict[str, Any]:
    """Сбор данных о рыночных парах из CoinMarketCap"""
    try:
        session = await get_http_session()
        market_data = await asyncio.get_event_loop().run_in_executor(
            None, CMC_market_pairs, symbol, 20
        )
        logger.info(f"CMC market pairs data collected for {symbol}")

        # Анализ: объем торгов
        market_pairs = market_data.get('data', {}).get('market_pairs', [])
        total_volume = sum(float(pair.get('quote', {}).get('USD', {}).get('volume_24h', 0))
                           for pair in market_pairs)

        analysis = {
            'total_volume_24h': total_volume,
            'exchange_count': len(market_pairs),
            'top_exchanges': [pair.get('exchange', {}).get('name') for pair in market_pairs[:3]]
        }

        return {
            "source": "cmc_market_pairs",
            "symbol": symbol,
            "data": market_data,
            "analysis": analysis,
            "error": None
        }
    except Exception as e:
        error_msg = f"CMC Market Pairs API error for {symbol}: {e}"
        logger.error(error_msg)
        return {"source": "cmc_market_pairs", "symbol": symbol, "data": None, "error": error_msg}


async def publish_to_redis(data: Dict[str, Any]):
    """Публикация данных в Redis Stream"""
    try:
        # Добавляем timestamp
        data['collected_at'] = datetime.now().isoformat()
        data['message_id'] = f"{data['source']}_{int(time.time() * 1000)}"

        # Конвертируем данные в JSON строку
        message_data = json.dumps(data, ensure_ascii=False, default=str)

        # Публикуем в Redis Stream с уникальным ID
        stream_id = await redis_client.xadd(
            "api_alerts",
            {"data": message_data},
            maxlen=1000  # Ограничиваем размер стрима
        )

        logger.info(f"Data from {data['source']} published to Redis Stream with ID: {stream_id}")

        # Сохраняем отдельно для быстрого доступа к последним данным (опционально)
        if data['source'] == 'ton_jettons':
            await redis_client.set('last_ton_jettons', message_data, ex=3600)
        elif data['source'] == 'cmc_listings':
            await redis_client.set('last_cmc_listings', message_data, ex=600)

    except Exception as e:
        logger.error(f"Failed to publish to Redis: {e}")


async def data_collection_cycle():
    """Один цикл сбора данных с разной периодичностью"""
    current_time = time.time()
    tasks = []

    # TON Jettons (каждые 30 минут)
    if current_time - DATA_SOURCES['ton_jettons']['last_run'] >= DATA_SOURCES['ton_jettons']['interval']:
        tasks.append(asyncio.create_task(collect_ton_jettons(50)))
        DATA_SOURCES['ton_jettons']['last_run'] = current_time

    # TON Jetton Details (каждый час для приоритетных jettons)
    if current_time - DATA_SOURCES['ton_jetton_details']['last_run'] >= DATA_SOURCES['ton_jetton_details']['interval']:
        for address in PRIORITY_JETTONS:
            tasks.append(asyncio.create_task(collect_ton_jetton_details(address)))
        DATA_SOURCES['ton_jetton_details']['last_run'] = current_time

    # TON Jetton Holders (каждые 2 часа для приоритетных jettons)
    if current_time - DATA_SOURCES['ton_jetton_holders']['last_run'] >= DATA_SOURCES['ton_jetton_holders']['interval']:
        for address in PRIORITY_JETTONS:
            tasks.append(asyncio.create_task(collect_ton_jetton_holders(address)))
        DATA_SOURCES['ton_jetton_holders']['last_run'] = current_time

    # TON Jetton Events (каждые 15 минут для приоритетных jettons)
    if current_time - DATA_SOURCES['ton_jetton_events']['last_run'] >= DATA_SOURCES['ton_jetton_events']['interval']:
        for address in PRIORITY_JETTONS:
            tasks.append(asyncio.create_task(collect_ton_jetton_events(address)))
        DATA_SOURCES['ton_jetton_events']['last_run'] = current_time

    # CMC Listings (каждые 5 минут)
    if current_time - DATA_SOURCES['cmc_listings']['last_run'] >= DATA_SOURCES['cmc_listings']['interval']:
        tasks.append(asyncio.create_task(collect_cmc_listings()))
        DATA_SOURCES['cmc_listings']['last_run'] = current_time

    # CMC Market Pairs (каждые 10 минут)
    if current_time - DATA_SOURCES['cmc_market_pairs']['last_run'] >= DATA_SOURCES['cmc_market_pairs']['interval']:
        tasks.append(asyncio.create_task(collect_cmc_market_pairs('TON')))
        tasks.append(asyncio.create_task(collect_cmc_market_pairs('BTC')))
        DATA_SOURCES['cmc_market_pairs']['last_run'] = current_time

    # Выполняем все задачи
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Публикуем результаты в Redis
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task failed: {result}")
            elif result and result.get('data') is not None:
                await publish_to_redis(result)


async def main_worker():
    """Основной рабочий процесс"""
    # Проверяем подключение к Redis
    try:
        await redis_client.ping()
        logger.info("Connected to Redis")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return

    logger.info("Starting data collection worker...")

    try:
        while True:
            start_time = time.time()

            # Выполняем цикл сбора данных
            await data_collection_cycle()

            # Ждем перед следующим циклом (30 секунд)
            await asyncio.sleep(30)

    except asyncio.CancelledError:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker error: {e}")
    finally:
        try:
            await redis_client.close()
            await close_http_session()
            logger.info("Disconnected from Redis and closed HTTP session")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    print("Starting enhanced data collection service...")
    print("Press Ctrl+C to stop")

    try:
        asyncio.run(main_worker())
    except KeyboardInterrupt:
        print("\nService stopped by user")
        logger.info("Service stopped by user")