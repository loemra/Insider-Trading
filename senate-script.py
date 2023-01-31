import asyncio
import aiohttp
import requests as r
import re
import json


async def getPeriodicTransactionReportURLS(session, start_date='01/01/2022', end_date='12/31/2022'):
    response = await session.get('https://efdsearch.senate.gov/search/home/')
    print(await response.text())
    csrftoken = session.cookie_jar.filter_cookies('https://efdsearch.senate.gov/')['csrftoken'].value
    
    payload = {
        'prohibition_agreement': '1',
        'csrfmiddlewaretoken': csrftoken
    }

    headers = {
        'Referer': 'https://efdsearch.senate.gov/search/'
    }

    await session.post('https://efdsearch.senate.gov/search/home/', data=payload, headers=headers)

    payload = {
        'first_name': '',
        'last_name': '',
        'report_type': '11',
        'submitted_start_date': start_date,
        'submitted_end_date': end_date,
        'csrfmiddlewaretoken': csrftoken
    }

    await session.post('https://efdsearch.senate.gov/search/', data=payload, headers=headers)

    payload = {
        'draw': '1',
        'columns[0][data]': '0',
        'columns[0][name]': '',
        'columns[0][searchable]': 'true',
        'columns[0][orderable]': 'true',
        'columns[0][search][value]': '',
        'columns[0][search][regex]': 'false',
        'columns[1][data]': '1',
        'columns[1][name]': '',
        'columns[1][searchable]': 'true',
        'columns[1][orderable]': 'true',
        'columns[1][search][value]': '',
        'columns[1][search][regex]': 'false',
        'columns[2][data]': '2',
        'columns[2][name]': '',
        'columns[2][searchable]': 'true',
        'columns[2][orderable]': 'true',
        'columns[2][search][value]': '',
        'columns[2][search][regex]': 'false',
        'columns[3][data]': '3',
        'columns[3][name]': '',
        'columns[3][searchable]': 'true',
        'columns[3][orderable]': 'true',
        'columns[3][search][value]': '',
        'columns[3][search][regex]': 'false',
        'columns[4][data]': '4',
        'columns[4][name]': '',
        'columns[4][searchable]': 'true',
        'columns[4][orderable]': 'true',
        'columns[4][search][value]': '',
        'columns[4][search][regex]': 'false',
        'order[0][column]': '1',
        'order[0][dir]': 'asc',
        'order[1][column]': '0',
        'order[1][dir]': 'asc',
        'start': '0',
        'length': '25',
        'search[value]': '',
        'search[regex]': 'false',
        'report_types': '[11]',
        'filer_types': '[]',
        'submitted_start_date': '{} 00:00:00'.format(start_date),
        'submitted_end_date': '{} 23:59:59'.format(end_date),
        'candidate_state': '',
        'senator_state': '',
        'office_id': '',
        'first_name': '',
        'last_name': '',
    }

    headers = {
        'Referer': 'https://efdsearch.senate.gov/search/',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-CSRFToken': csrftoken,
    }

    response = await session.post('https://efdsearch.senate.gov/search/report/data/', data=payload, headers=headers)
    try:
        j = await response.json()
    except Exception:
        return []
    total_records = j['recordsTotal']
    total_draws = total_records//25 + (total_records%25 != 0)

    regex = r'a href=\"(/search/view/(.*?)/.*?)\"'

    urls = []
    for i in range(1, total_draws+1):
        payload['draw'] = '{}'.format(i)
        payload['start'] = '{}'.format((i-1)*25)
        response = await session.post('https://efdsearch.senate.gov/search/report/data/', data=payload, headers=headers)
        j = await response.json()

        for k in range(len(j['data'])):
            match = re.search(regex, j['data'][k][3])
            if match.group(2) != 'ptr':
                continue
            urls.append('https://efdsearch.senate.gov{}'.format(match.group(1)))

    print('urls retrieved')
    return urls


async def getPeriodicTransactionReportText(session, url):
    async with session.get(url) as response:
        text = await response.text()
        return text


async def getPeriodicTransactionReportTextsSlow(session, urls):
    texts = []
    for url in urls:
        text = await getPeriodicTransactionReportText(session, url)
        if 'Sorry' in text:
            print('rate limited on {}'.format(url))
            continue
        texts.append(text)
        print('retrieved {}'.format(url))

    return texts


async def getPeriodicTransactionReportTexts(session, urls):
    ret = await asyncio.gather(*[getPeriodicTransactionReportText(session, url) for url in urls])
    print("Finalized all. Return is a list of len {} outputs.".format(len(ret)))
    return ret


def parsePeriodicTransactionReportText(text):
    regex = r'<h2 class=\"filedReport\">.*?\((.*?)\).*?<\/h2>'
    match = re.search(regex, text, re.DOTALL)

    name = ''
    if match is None:
        print('No name found.')
        pass
    else:
        name = match.group(1)

    filer_information = {
        'name': name
    }

    regex = r'<p class=\"muted\">.*?Filed\s*(.*?)\s'
    match = re.search(regex, text, re.DOTALL)
    notification_date = ''
    if match is not None:
        notification_date = match.group(1)

    regex = r'<tr>(.*?)</tr>'
    matches = re.findall(regex, text, re.DOTALL)

    trades = []
    for match in matches:
        regex = r'\s*(?:<td>.*?</td>.*?){9}'
        if re.match(regex, match, re.DOTALL) is None:
            continue

        regex = r'<td>\s*(.*?)\s*</td>'
        sub_matches = re.findall(regex, match, re.DOTALL)
        info = []
        for match in sub_matches:
            info.append(match)

        if 'Stock' not in info[5] or 'yahoo' not in info[3]:
            continue

        transaction_type = ''
        if 'Sale' in info[6]:
            transaction_type = 'S'
        elif 'Purchase' in info[6]:
            transaction_type = 'P'
        else:
            continue

        regex = r'>(.*?)</a'
        ticker_match = re.search(regex, info[3])
        if ticker_match is None:
            continue
        ticker = ticker_match.group(1)

        trade_information = {
            'ticker': ticker,
            'transaction_type': transaction_type,
            'transaction_date': info[1],
            'notification_date': notification_date,
            'amount': ''.join(info[7].split())
        }

        trades.append(trade_information)

    if len(trades) == 0:
        print("No trades")
        return None

    report = {'filer_information': filer_information, 'trades': trades}
    return report


def saveTransactionsToJSONFile(texts, json_filename):
    transactions = []
    for text in texts:
        report = parsePeriodicTransactionReportText(text)
        if report is not None:
            transactions.append(report)
    j = json.dumps(transactions)

    with open(json_filename, 'w') as file:
        file.write(j)

async def run():
    for i in range(2016, 2023):
        print('working on {}'.format(i))
        async with aiohttp.ClientSession() as session:
            urls = await getPeriodicTransactionReportURLS(session, '01/01/{}'.format(i), '12/31/{}'.format(i))
            texts = await getPeriodicTransactionReportTextsSlow(session, urls)
            with open('{}.txt'.format(i), 'w') as file:
                file.write(''.join(texts))
            saveTransactionsToJSONFile(texts, 'senate-transactions-{}.json'.format(i))


run()