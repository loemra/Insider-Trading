from PyPDF2 import PdfReader
import os
import tempfile
import re
import xml.etree.ElementTree as ET
import requests as r
from zipfile import ZipFile
import json


def parsePeriodicTransactionReport(pdf_contents):
    text = ''

    fd, temp_path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, 'wb') as file:
            file.write(pdf_contents)
            reader = PdfReader(temp_path)

            for page in reader.pages:
                text += page.extract_text()
    finally:
        os.remove(temp_path)

    filer_regex = r'name:\s*(.*?)\s*status:\s*(.*?)\s*state/district:\s*(.*?[0-9]+)'
    matches = re.finditer(filer_regex, text, re.DOTALL | re.IGNORECASE)

    filer_information = {}
    for match in matches:
        filer_information = {'name': match.group(1), 'status': match.group(2), 'state_district': match.group(3)}
        break

    transaction_regex = r'\(([A-Za-z]+)\).*?(?:\[([A-Z]*)\])?.*?([S|P]).*?([0-9]+?\/[0-9]+?\/[0-9]{4}).*?([0-9]+?\/[0-9]+?\/[0-9]{4}).*?(\$[0-9|,]+.*?\$[0-9|,]+)'
    matches = re.finditer(transaction_regex, text, re.DOTALL)

    trades = []
    for match in matches:
        if match.group(2) is not None and match.group(2) != 'ST':
            continue
        
        trade_information = {
            'ticker': match.group(1).upper().strip(),
            'transaction_type': match.group(3),
            'transaction_date': match.group(4),
            'notification_date': match.group(5),
            'amount': ''.join(match.group(6).split())
        }
        trades.append(trade_information)

    if len(trades) == 0:
        return None

    report = {'filer_information': filer_information, 'trades': trades}
    return report


def parseFinancialDisclosureReport(xml_filename):
    tree = ET.parse(xml_filename)
    root = tree.getroot()

    document_ids = []
    for member in root.findall('./Member'):
        if member.find('./FilingType').text != 'P':
            continue
        document_ids.append(member.find('./DocID').text)

    return document_ids

# %%
import requests as r

def getPeriodicTransactionReport(document_id, year='2022'):
    response = r.get('https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{}/{}.pdf'.format(year, document_id))

    if response.status_code == 200:
        return response.content
        
    response = r.get('https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{}/{}.pdf'.format(year, document_id))

    if response.status_code == 200:
        return response.content

    print('Unable to get Periodic Transaction Report {}'.format(document_id))


def saveFinancialClosureReport(year='2022'):
    response = r.get('https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{}FD.ZIP'.format(year))

    if response.status_code != 200:
        print('Unable to get Financial Closure Report for the web: {}'.format(year))
        return

    extract_file = '{}FD.xml'.format(year)

    fd, temp_path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, 'wb') as file:
            file.write(response.content)
            with ZipFile(temp_path, 'r') as zip_ref:
                zip_ref.extract(extract_file)
    finally:
        os.remove(temp_path)

    return extract_file


def saveTransactionsToJSONFile(document_ids, json_filename, year='2022'):
    transactions = []
    for id in document_ids:
        pdf_contents = getPeriodicTransactionReport(id, year)
        if pdf_contents is None:
            continue
        report = parsePeriodicTransactionReport(pdf_contents)
        if report is not None:
            transactions.append(report)
            print('Parsed {}'.format(id))
        else:
            print('Unable to parse {}'.format(id))
    j = json.dumps(transactions)

    with open(json_filename, 'w') as file:
        file.write(j)


for i in range(2016, 2023):
    year = '{}'.format(i)
    print('working through {}'.format(year))
    report = saveFinancialClosureReport(year)
    document_ids = parseFinancialDisclosureReport(report)
    saveTransactionsToJSONFile(document_ids, 'congressional-transactions-{}.json'.format(year), year)