import re
import html
import json
import logging

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """
    Очищает текст от водяных знаков и артефактов нейросети
    """
    if not text or not isinstance(text, str):
        return text

    # 1. Декодируем HTML entities
    cleaned = html.unescape(text)

    # 2. Удаляем только специфические артефакты нейросети, не трогая структуру JSON
    neural_artifacts = [
        r'【\d+:\d+†(source|source)】',
        r'‹+.*?›+',
        r'«+.*?»+',
        r'⇥.*?⇤',
        r'<.*?>',
    ]

    for pattern in neural_artifacts:
        cleaned = re.sub(pattern, '', cleaned)

    # 3. Удаляем только эмодзи и специфические символы
    special_chars = [
        '†', '⇥', '⇤', '‹', '›', '«', '»',
        '✨', '🚀', '📈', '📊', '💱', '💎', '🔥', '⭐', '🌟',
        '▪', '•', '→', '←', '↑', '↓', '↔', '↕', '⇒', '⇔', '⇄', '⇆',
    ]

    for char in special_chars:
        cleaned = cleaned.replace(char, '')

    # 4. Удаляем лишние пробелы и переносы строк
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


def clean_json_response(text: str) -> str:
    """
    Специальная очистка для JSON-ответов
    """
    # Сначала пытаемся найти JSON в тексте
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if not json_match:
        return ''

    cleaned = json_match.group(0)

    # Удаляем только управляющие символы
    cleaned = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', cleaned)

    # Дополнительная очистка от артефактов
    cleaned = clean_text(cleaned)

    return cleaned


def safe_json_parse(text: str) -> dict:
    """
    Безопасный парсинг JSON
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        return {}