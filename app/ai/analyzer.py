import json

from app.ai.provider import chat
from app.ai.parser import parse_json


def analyze(text: str):

    prompt = f"""
Sen profesyonel bir otomotiv editörüsün.

Görevin aşağıdaki haberi analiz etmektir.

Sadece JSON döndür.

Kurallar:

- brand sadece marka adı olsun.
- model sadece model adı olsun.
- summary mutlaka TÜRKÇE olsun.
- summary en fazla 2 cümle olsun.
- importance 1 ile 10 arasında sayı olsun.

Kategori sadece aşağıdakilerden biri olabilir:

EV
Hybrid
ICE
SUV
Sedan
Hatchback
Pickup
Battery
Charging
Software
Recall
Factory
Motorsport
Financial
Other

Kategori seçerken haberin ANA KONUSUNU seç.

Örnek:

Elektrikli otomobil tanıtımı → EV

Batarya teknolojisi → Battery

Yazılım güncellemesi → Software

Geri çağırma → Recall

Fabrika yatırımı → Factory

Motor sporları → Motorsport

Finansal haber → Financial

Haber:

{text}
"""

    response = chat(prompt)

    return parse_json(response)