import re

# Простой список матов (в реальности — можно загрузить из файла или ML)
BAD_WORDS = ["хуй", "бля", "пизд", "сука", "ебан", "нахуй"]

def contains_bad_words(text: str) -> bool:
    text_lower = text.lower()
    return any(re.search(rf"\b{word}", text_lower) for word in BAD_WORDS)

def censor_text(text: str) -> str:
    def replace_match(match):
        return "*" * len(match.group())
    
    text_lower = text
    result = text
    for word in BAD_WORDS:
        pattern = rf"\b{word}\w*\b"
        result = re.sub(pattern, replace_match, result, flags=re.IGNORECASE)
    return result