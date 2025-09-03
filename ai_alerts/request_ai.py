# ai_alerts/request_ai.py
from openai import OpenAI
from text_cleaner import clean_text, clean_json_response, safe_json_parse
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


client = OpenAI(
  base_url="https://neuroapi.host/v1",
  api_key="sk-0ADepEJvpCXBacg1z54pYrkY6v1nb2RY0MHmMMybLyXACzrE",
)

global_rule = {
    "role": "system",
    "content": """Твоя задача: Сделать Событие-новость или новости, которые я потом передам в микросервис. 

ВАЖНО: Ответ должен быть строго в формате JSON с двойными кавычками! А если НОВОСТЕЙ МНОГО, много записей, много информации - делай много новостей. НО НЕ ЕДЛАЙ ИХ ПО ПУСТЯКАМ, только РЕАЛЬНЫЕ новости.
Пример правильного ответа:
{"text": "Цена биткоина выросла на 11% за 24 часа!", "tags": ["Биткоин", "Криптовалюта", "рост цены"]}

Правила:
1. Сухой технический текст
2. Используй только двойные кавычки для JSON
3. Не добавляй никакого дополнительного текста кроме JSON
4. Теги должны быть на русском языке, одно-два слова
5. Новость должна быть основана на предоставленных данных, а так же ДОПУСКАЕТСЯ И ПООЩЕРЯЕТСЯ поиск АКЕТУАЛЬНОЙ информации самому. Главное - Актуальные данные 2025 года. Но предоставленные данные - главная истина
6. не зацикливайся на Битке. Делай НЕРПЕДСКАЗУЕМЫе новости, и пиши ол битке тольько в случае реальбных аномалисй
7. Делай минимум 2 РАЗНЫХ новостей из контекста полученного. Ты можншь получить на вход листинги и JETTONS - ткоены блокчейна TON
8. Отправляй новости одним массивом
 [{"text": "Новость 1", "tags": ["Тэг1", "Тэг2"]},{"text": "Новость 2", "tags": ["Тэг3", "Тэг4"]}]
 
 Новость красиво оформи, например:
 🚨 АЛЕРТ: Резкий рост цены! 🚀

Токен: BTC  
За последние 24 часа: +7.2% (с 58,500 USDT до 62,700 USDT)  
Текущая цена: 62,700 USDT  
Волатильность: Высокая (диапазон: 57,800 - 63,200 USDT)  
AI-прогноз: Ожидается дальнейший рост до 65,000 USDT в ближайшие 12 часов с вероятностью 68%. Возможен откат на 5-8% при негативных новостях.  
Рекомендация: Купить на сумму до 15% от портфеля, установить стоп-лосс на -3%. Проверь риски rug-pull: Нет подозрений (ликвидность заблокирована)
*Данные на 26 августа 2025. Не финансовый совет — торгуй на свой риск!*
переносы строки делай , например, \+n
"""
}


def request(content):
    completion = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[global_rule,
                  {"role": "user", "content": content}
                  ],
    )
    raw_response = completion.choices[0].message.content
    logger.info(f"Raw response from AI: {raw_response}")

    cleaned_response = clean_json_response(raw_response)
    if not cleaned_response:
        logger.error("Empty response after cleaning")
        return '{"error": "Empty response after cleaning"}'

    logger.info(f"Cleaned response from AI: {cleaned_response}")

    # Парсим JSON для проверки валидности
    parsed_data = safe_json_parse(cleaned_response)
    logger.info(f"Parsed response from AI: {parsed_data}")

    if parsed_data:
        return json.dumps(parsed_data, ensure_ascii=False)
    else:
        return '{"error": "Invalid JSON response from AI"}'