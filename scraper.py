import requests
import sys
from lxml import etree
import re
import os
from datetime import date
import scraperwiki
from slackclient import SlackClient
from os import environ
import hashlib
import simplejson as json


def get_json_from_url(url):
    call_url = "https://hansard-parser.g0vhk.io/parse"
    body = {'url': url}
    r = requests.post(call_url, json=body)
    return r.json()


def create_image(data): 
    print(data.keys())


def upload_hansard(hansard_json, legco_api_token):
    headers = {'Content-Type': 'application/json', 'Authorization': 'Token ' + legco_api_token}
    print(hansard_json)
    r = requests.put("https://api.g0vhk.io/legco/upsert_hansard/", json=hansard_json, headers=headers)
    print(r.json())
    if r.ok:
        print('Uploaded.')
    else:
        print('Upload error.')


def crawl(token, channel, legco_api_token):
    today = date.today()
    year = today.year
    if today.month < 10:
        year = year - 1
    current_year = year - 2000
    year_start = (current_year // 4) * 4
    year_end = year_start + 4
    url = "https://www.legco.gov.hk/general/chinese/counmtg/yr%.2d-%.2d/mtg_%.2d%.2d.htm" % (year_start, year_end, current_year, current_year + 1)
    r = requests.get(url)
    r.encoding = "utf-8"
    root = etree.HTML(r.text)
    cm_dates = [re.match(r'.*date=([^&]+)', link).group(1) for link in root.xpath("//a/@href") if link.find("date=") != -1]
    print(url)
    print(cm_dates)

    slack = SlackClient(token)
    for d in cm_dates:
        rundown_request = requests.get('http://www.legco.gov.hk/php/hansard/chinese/rundown.php?date=%s&lang=2' % (d))
        rundown_html = rundown_request.text.split('\n')
        for line in rundown_html:
            if line.find(".pdf") != -1:
                var, url = line.split(" = ")
                url = url.strip()
                pdf_url = "https:" + url.replace("\"", "").replace(";", "").replace("#", "").replace("\\", "")
                file_name = pdf_url.split('/')[-1]
                year , month, day = d.split("-")
                existed = False
                key = hashlib.md5(pdf_url.encode('utf-8')).hexdigest()
                try:
                    existed = len(scraperwiki.sqlite.select('* from data where hash = "%s"' % key)) > 0
                except:
                    pass
                if existed:
                    continue
                data = {
                    'year': year,
                    'month': month,
                    'day': day,
                    'url': pdf_url,
                    'hash': key
                }
                text = "New Hansard is available at %s." % (pdf_url)
                hansard_json = get_json_from_url(pdf_url)
                if channel:
                    slack.api_call(
                            "chat.postMessage",
                            channel=channel,
                            text=text
                    )
                else:
                    print('Skipping Slack')
                if legco_api_token:
                    upload_hansard(hansard_json, legco_api_token)
                else:
                    print('Skipping upsert')
                print("new PDF url %s" % pdf_url)
                scraperwiki.sqlite.save(unique_keys=['hash'], data=data)


TOKEN = environ.get('MORPH_TOKEN', None)
CHANNEL = environ.get('MORPH_CHANNEL', None)
LEGCO_API_TOKEN = environ.get('MORPH_LEGCO_API_TOKEN', None)
crawl(TOKEN, CHANNEL, LEGCO_API_TOKEN)
