# parse mts
## Serverless python MTS tariffs parser

Serverless парсер тарифов МТС

работающий в Yandex Cloud Functions.

#### Что делает:

Получает список тарифов с сайта МТС, парсит и записывает данные в JSON файл.

Фронтенд работает в Object Storage, при нажатии на кнопку запускает скрипт, который обновляет

JSON файл с тарифами.

Демо: https://parse-mts.website.yandexcloud.net/

#### Технологии:

- Python
- BeautifulSoup
- HTML
- Yandex Object Storage
- Yandex Cloud Functions

#### Как запустить:

Для запуска локально нужно склонировать репозиторий:

`
pip install -r requirements.txt
`

запустить скрипт:

`
python main.py
`

запустить сервер:

`
python -m http.server
`

Страница с тарифами будет доступна п адресу:

`
http://localhost:8000/
`