from urllib.request import urlopen as uOp
from bs4 import BeautifulSoup as suop
from time import strptime
from csv import writer
import pandas as pd
import locale
import threading
from influxdb import InfluxDBClient
import logging
logging.basicConfig(format='%(asctime)s - %(levelname)s:%(message)s', level=logging.INFO, datefmt='%d/%m/%Y %H:%M:%S')
_logger = logging.getLogger(__name__)

locale.setlocale(locale.LC_ALL, '')

# create influxdb client
client_inf = InfluxDBClient('scraper_influxdb', 8086, 'root', 'root', 'corona')

# url open frequency
wait = 10

# url to open
url = 'https://covid19.saglik.gov.tr'


def main(url, cli=client_inf):
    # create client to open url
    client = uOp(url)
    html_cont = client.read()
    client.close()

    parse = suop(html_cont, 'html.parser')

    date_div = parse.findAll('div', {'class': 'takvim text-center'})
    date_list = date_div[0].findAll('p')

    mnth_dict = {'ocak': 1, 'şubat': 2, 'mart': 3, 'nisan': 4, 'mayıs': 5, 'haziran': 6, 'temmuz': 7, 'ağustos': 8,
                 'eylül': 9, 'ekim': 10, 'kasım': 11, 'aralık': 12}

    if 'İ' in date_list[1].text:
        mnth_num = mnth_dict[date_list[1].text.replace('İ', 'I').lower()]
    elif 'I' in date_list[1].text:
        mnth_num = mnth_dict[date_list[1].text.lower().replace('i', 'ı')]
    else:
        mnth_num = mnth_dict[date_list[1].text.lower()]

    date = date_list[2].text + '-' + '0' + str(mnth_num) + '-' + date_list[0].text + 'T00:00:00Z'

    data_dict = {}

    tot_case_divs = parse.findAll('div', {'class': 'col-6 col-sm-6'})
    daily_case_divs = parse.findAll('div', {'class': 'col-lg-6 col-md-6 col-sm-12'})

    for i in tot_case_divs[0].div.findAll('li'):
        d_key_tot = i.findAll('span')[0].text.replace(' ', '').replace('\n', '').replace('\r', ' ').strip()
        d_val_tot = i.findAll('span')[1].text.replace('.', '')
        data_dict[d_key_tot] = int(d_val_tot)

    for i in daily_case_divs[1].div.findAll('li'):
        d_key_daily = i.findAll('span')[0].text.replace(' ', '').replace('\n', '').replace('\r', ' ').strip()
        d_val_daily = i.findAll('span')[1].text.replace('.', '')
        data_dict[d_key_daily] = int(d_val_daily)

    def append_to_csv(file_name, list_of_elem):
        with open(file_name, 'a+', newline='') as write_obj:
            csv_writer = writer(write_obj)
            csv_writer.writerow(list_of_elem)

    fin_json = [{
        'measurement': 'corona',
        'time': date,
        'fields': {
            'total_cases': data_dict['TOPLAM VAKA SAYISI'],
            'total_death': data_dict['TOPLAM VEFAT SAYISI'],
            'total_recovered': data_dict['TOPLAM İYİLEŞEN HASTASAYISI'],
            'total_tests': data_dict['TOPLAM TEST SAYISI'],
            'daily_cases': data_dict['BUGÜNKÜ VAKA SAYISI'],
            'daily_recovered': data_dict['BUGÜNKÜ İYİLEŞEN SAYISI'],
            'daily_tests': data_dict['BUGÜNKÜ TEST SAYISI'],
            'daily_death': data_dict['BUGÜNKÜ VEFAT SAYISI'],
            'total_ic_pat': data_dict['TOPLAM YOĞUNBAKIM HASTASAYISI'],
            'total_intubated_pat': data_dict['TOPLAM ENTUBE HASTASAYISI']
        }
    }]

    try:
        check_last_entry_date = cli.query('select last(total_cases) from corona')

        if len(list(check_last_entry_date.get_points(measurement='corona'))) == 0:
            cli.write_points(fin_json, time_precision='n')
            _logger.info(f'First entry to the database has appended.')
        elif len(list(check_last_entry_date.get_points(measurement='corona'))) > 0:
            check_last_entry_date = list(check_last_entry_date.get_points(measurement='corona'))[0]['time']
            _logger.info(f'fetched date from DB {check_last_entry_date}')
            if date != check_last_entry_date:
                cli.write_points(fin_json, time_precision='n')
                _logger.info(f'Another entry appended. The date is {date}')
            else:
                _logger.info(f'Last entry date is equal to fetched date from web page. Not appended!')
    except Exception as e:
        _logger.error(f'Error! {e}')


ticker = threading.Event()
while not ticker.wait(wait):
    main(url=url)
