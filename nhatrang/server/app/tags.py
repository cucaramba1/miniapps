COMPLAINTS = ["mold_smell", "insects", "noise", "dirty", "utilities",
              "language_gap", "mismatch", "safety"]
POSITIVE = ["ru_reception", "en_reception", "market_near", "quiet", "clean"]
ALL_TAGS = set(COMPLAINTS) | set(POSITIVE)
LABELS_RU = {
    "mold_smell": "Плесень / запах",
    "insects": "Насекомые",
    "noise": "Шум",
    "dirty": "Грязно",
    "utilities": "Проблемы с коммуналкой",
    "language_gap": "Не говорят на понятном языке",
    "mismatch": "Не соответствует описанию",
    "safety": "Небезопасно",
    "ru_reception": "Ресепшн говорит по-русски",
    "en_reception": "Ресепшн говорит по-английски",
    "market_near": "Рынок рядом",
    "quiet": "Тихо",
    "clean": "Чисто",
}
