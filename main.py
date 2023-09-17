import json
import re
import requests
import boto3
import os

from bs4 import BeautifulSoup as bs

url = 'https://moskva.mts.ru/personal/mobilnaya-svyaz/tarifi/vse-tarifi/'

headers = {
    'Accept': '*/*',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
}

USE_S3 = False


session = boto3.session.Session()
s3 = session.client(
    service_name='s3',
    endpoint_url=os.getenv('S3_ENDPOINT'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
)


def write_s3(field, text) -> None:
    s3.put_object(Bucket=os.getenv('S3_FIELDS', 'parse-mts'), Key=field, Body=text)


def get_actual_tariffs():
    response = requests.get(url, headers=headers)
    parse = bs(response.text, 'lxml')
    data = parse.find('script', string=re.compile("actualTariffs"))
    tariffs = json.loads(data.text[data.text.find("{"):data.text.rfind("}") + 1])
    return tariffs['actualTariffs']


def parse_mts(event, context):
    actual = get_actual_tariffs()
    parsed_tariffs = []

    def get_annotation(tariff):
        if "subscriptionFeeAnnotationSettings" in tariff:
            return tariff["subscriptionFeeAnnotationSettings"].get("text", None)
        return None

    def get_link(tariff):
        if "productInfoLink" in tariff and "value" in tariff["productInfoLink"]:
            return tariff["productInfoLink"]["value"]
        return f'{url}{tariff.get("alias")}'

    def get_subscription_fee(tariff):
        def _get_value(item):
            values = ("discountFee", "subscriptionFee", )
            for value in values:
                if value in item:
                    return item[value]["numValue"]
            return None

        if _get_value(tariff):
            return _get_value(tariff)
        if tariff["tariffType"] == "Mobile":
            if "customizingType" in tariff:
                if tariff["customizingType"] == "Configurator":
                    for package in tariff["configurableTariffSettings"]["packages"]:
                        if package["isDefault"]:
                            return _get_value(package)
                elif tariff["customizingType"] == "Parametrized":
                    if "parametrizedTariffSettings" in tariff and (
                            "defaultPackagePrice" in tariff["parametrizedTariffSettings"]
                    ):
                        return int(tariff["parametrizedTariffSettings"]["defaultPackagePrice"])
        return 0

    def get_unit(item, parameter):

        if "customizingType" in item:
            if item["customizingType"] == "Configurator":
                regulator = None
                for package in item["configurableTariffSettings"]["packages"]:
                    if package["isDefault"]:
                        regulator = package["regulatorsOptionsIds"][0]
                for option in item["configurableTariffSettings"]["regulators"][0]["options"]:
                    if option["optionId"] == regulator:
                        for quota in option["quotas"]:
                            if parameter == quota["baseParameter"]:
                                return quota["numValue"]
            elif item["customizingType"] == "Parametrized":
                params = {
                    "MinutesPackage": "Calls",
                    "InternetPackage": "Internet",
                    "MessagesPackage": "Sms",
                }
                find_param = params.get(parameter)
                if "parametrizedTariffSettings" in item and (
                        "parametrizedOptions" in item["parametrizedTariffSettings"]
                ):
                    for option in item["parametrizedTariffSettings"]["parametrizedOptions"]:
                        if find_param == option["serviceType"]:
                            return f'{int(option["rangeSettings"]["defaultValue"])}'
                # А за эти тарифы с вас мерчёвые носки

        if "productCharacteristics" in item and item["productCharacteristics"]:
            for unit in item["productCharacteristics"]:
                if parameter == unit["baseParameter"]:
                    return int(unit["numValue"])
        return None

    def get_benefits(tariff):
        if "benefitsDescription" in tariff and "description" in tariff["benefitsDescription"]:
            return tariff["benefitsDescription"]["description"]

    def clear_text(text):
        pattern = {
            '&nbsp;': ' ',
            '&mdash;': '',
            '&#8381;': '₽',
            '<nobr>': '',
            '</nobr>': '',
        }
        if text:
            for key in pattern.keys():
                text = text.replace(key, pattern[key])
        return text

    for tariff in actual:

        new_tariff = {
            "tariffType": tariff.get("tariffType"),
            "title": tariff.get("title"),
            "description": clear_text(tariff.get("description")),
            "Annotation": clear_text(get_annotation(tariff)),
            "subscriptionFee": get_subscription_fee(tariff),
            "tariffUrl": get_link(tariff),
            "cardImageUrl": f'https:{tariff.get("cardImageUrl")}',
            "MinUnit": get_unit(tariff, "MinutesPackage"),
            "smsUnit": get_unit(tariff, "MessagesPackage"),
            "gbUnit": get_unit(tariff, "InternetPackage"),
            "gbitUnit": get_unit(tariff, "MaxSpeed"),
            "channelsUnit": get_unit(tariff, "TvChannels"),
            "benefits": clear_text(get_benefits(tariff)),

        }
        parsed_tariffs.append(new_tariff)

    if USE_S3:
        write_s3('data.json', json.dumps(parsed_tariffs))
    else:
        with open('data.json', 'w') as file:
            json.dump(parsed_tariffs, file, indent=4, ensure_ascii=False, )

    return {
        'statusCode': 200,
        'body': 'parse complete',
    }


if __name__ == '__main__':
    parse_mts(event=None, context=None)
