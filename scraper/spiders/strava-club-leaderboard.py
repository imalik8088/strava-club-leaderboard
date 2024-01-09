# -*- coding: utf-8 -*-
import re

import scrapy
from scrapy.http import FormRequest
from tinydb import TinyDB, Query
from tinydb.database import Table

from .credentials import strava


class StravaSpider(scrapy.Spider):
    BASE_URL = 'https://www.strava.com'
    name = 'strava'
    allowed_domains = ['strava.com']
    start_urls = ['https://www.strava.com/login']
    cookies = {}
    db: Table = None
    Leaderboard = Query()
    club_id = None
    year = None
    headers = {
        'authority': 'www.strava.com',
        'pragma': 'no-cache',
        'cache-control': 'no-cache',
        'sec-ch-ua': 'Google Chrome";v="87", " Not;A Brand";v="99", "Chromium";v="87"',
        'accept': 'text/javascript, application/javascript, application/ecmascript, application/x-ecmascript',
        'sec-ch-ua-mobile': '?0',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_1_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
        'Accept-Encoding': 'gzip, deflate, sdch',
        'Accept-Language': 'en-US,en;q=0.8'
    }

    def parse(self, response):
        self.logger.info('Visiting %s...' % self.start_urls[0])
        authenticity_token = response.xpath(
            '//*[@name="authenticity_token"]/@value').extract_first()
        yield FormRequest.from_response(response,
                                        formdata={
                                            'authenticity_token': authenticity_token,
                                            'email': strava['user'],
                                            'password': strava['password']},
                                        meta={'dont_redirect': True, 'handle_httpstatus_list': [302]},
                                        callback=self.after_login)

    def __init__(self, club_id, year=2023, **kwargs):
        self.club_id = club_id
        self.year = year
        self.db = TinyDB(f"./db/strava-leaderboard-{club_id}-{year}.json")

    def after_login(self, response):
        cookie = response.headers.getlist('Set-Cookie')[0].decode("utf-8").split(';')[0]
        self.cookies = dict(cookie.split("=") for x in cookie.split(";"))
        self.logger.info(f"[Cookie] {self.cookies}")
        self.logger.info('Logged in... ')

        club_url = f"{self.BASE_URL}/clubs/{self.club_id}/members"
        yield scrapy.Request(url=club_url, callback=self.club_member_overview)

    def club_member_overview(self, response):
        MEMBER_SELECTOR = 'div.border-top > ul.list-athletes > li > div.text-headline'
        for list_user_block in response.css(MEMBER_SELECTOR):
            profile_url = self.BASE_URL + list_user_block.css("a::attr(href)").extract_first()
            comparision_data_url = f"{profile_url}/profile_sidebar_comparison?hl=en-US&ytd_year={self.year}"
            user_name = list_user_block.css("a::text").extract_first()

            user_id = re.findall(r'athletes/(\d*)', profile_url, re.M | re.I)[0]
            self.db.upsert({'user_id': user_id, 'name': user_name, 'profile_url': profile_url}, self.Leaderboard.user_id == user_id)

            yield scrapy.Request(url=comparision_data_url,
                                 headers=self.headers,
                                 cookies=self.cookies,
                                 callback=self.profile_crawler)

        NEXT_PAGE_SELECTOR = 'nav > ul.pagination > li.next_page > a::attr(href)'
        if (len(response.css(NEXT_PAGE_SELECTOR)) > 0):
            next_page_path = response.css(NEXT_PAGE_SELECTOR).extract_first()
            next_page_url = f"{self.BASE_URL}{next_page_path}"
            self.logger.info(f"next page: {next_page_url}")
            yield scrapy.Request(url=next_page_url, callback=self.club_member_overview)

    def profile_crawler(self, response):
        user_id = re.findall(r'athletes/(\d*)', response.request.url, re.M | re.I)[0]

        # running
        sport_tab_index_for_run = self._get_sport_tab_index(response, 'Run')
        running_km = 0
        running_hours = 0
        if sport_tab_index_for_run != None:
            running_km = self._get_running_kilometers(user_id, response, sport_tab_index_for_run)
            running_hours = self._get_running_hours(user_id, response, sport_tab_index_for_run)

        # cycling
        sport_tab_index_for_cycling = self._get_sport_tab_index(response, 'Ride')
        cycling_km = 0
        cycling_hours = 0
        cycling_elevation = 0
        if sport_tab_index_for_cycling != None:
            cycling_km = self._get_cycling_kilometers(user_id, response, sport_tab_index_for_cycling)
            cycling_elevation = self._get_cycling_elevation(user_id, response, sport_tab_index_for_cycling)
            cycling_hours = self._get_cycling_hours(user_id, response, sport_tab_index_for_cycling)

        # swimming
        sport_tab_index_for_swim = self._get_sport_tab_index(response, 'Swim')
        swim_km = 0
        swim_hours = 0
        if sport_tab_index_for_swim != None:
            swim_km = self._get_swimming_meters(user_id, response, sport_tab_index_for_swim)
            swim_hours = self._get_swimming_hours(user_id, response, sport_tab_index_for_swim)


        self.db.upsert({
            'cycling_distance_in_km': cycling_km,
            'cycling_duration_in_minute': cycling_hours,
            'cycling_elevation_in_meter': cycling_elevation,
            'running_distance_in_km': running_km,
            'running_duration_in_minute': running_hours,
            'swimming_distance_in_meter': swim_km,
            'swimming_duration_in_minute': swim_hours
        }, self.Leaderboard.user_id == user_id)

        self.logger.debug(f"Done for {response.request.url}")

    def _get_sport_tab_index(self, response, sport_activity) -> str | None:
        RUNNING_SELECTOR = 'button.selected[title="%s"]' % sport_activity
        css_classes_of_activity = response.css(RUNNING_SELECTOR).xpath("@class").extract()
        pattern = r'sport-\d+-tab'
        css_classes_in_list = " ".join(css_classes_of_activity).split(" ")
        matching_items = [item for item in css_classes_in_list if re.match(pattern, item)]
        self.logger.debug('Found css class %s for sport activity %s' % (matching_items, sport_activity))

        if len(matching_items) > 0:
            return matching_items[0].split("-tab")[0]
        else:
            return None

    def _get_swimming_hours(self, user_id, response, sport_tab_index):
        HOURS_TOTAL_SELECTOR = 'tbody#%s-ytd > tr:nth-child(3) > td:nth-child(2)' % sport_tab_index
        raw_time = response.css(HOURS_TOTAL_SELECTOR).extract_first()
        hours_and_minutes = re.findall(r'(\d{1,})', raw_time, re.M | re.I)
        minutes_from_hours = int(hours_and_minutes[0]) * 60
        minutes = int(hours_and_minutes[1])
        total_minutes = minutes_from_hours + minutes
        self.logger.info(f"[Cycling] {hours_and_minutes[0]} hours and {hours_and_minutes[1]} minutes")
        return total_minutes

    def _get_cycling_hours(self, user_id, response, sport_tab_index):
        CYCLING_HOURS_TOTAL_SELECTOR = 'tbody#%s-ytd > tr:nth-child(4) > td:nth-child(2)' % sport_tab_index
        raw_time = response.css(CYCLING_HOURS_TOTAL_SELECTOR).extract_first()
        hours_and_minutes = re.findall(r'(\d{1,})', raw_time, re.M | re.I)
        minutes_from_hours = int(hours_and_minutes[0]) * 60
        minutes = int(hours_and_minutes[1])
        total_minutes = minutes_from_hours + minutes
        self.logger.info(f"[Cycling] {hours_and_minutes[0]} hours and {hours_and_minutes[1]} minutes")
        return total_minutes

    def _get_running_hours(self, user_id, response, sport_tab_index):
        CYCLING_HOURS_TOTAL_SELECTOR = 'tbody#%s-ytd > tr:nth-child(3) > td:nth-child(2)' % sport_tab_index
        raw_time = response.css(CYCLING_HOURS_TOTAL_SELECTOR).extract_first()
        hours_and_minutes = re.findall(r'(\d{1,})', raw_time, re.M | re.I)
        minutes_from_hours = int(hours_and_minutes[0]) * 60
        minutes = int(hours_and_minutes[1])
        total_minutes = minutes_from_hours + minutes
        self.logger.info(f"[Running] {hours_and_minutes[0]} hours and {hours_and_minutes[1]} minutes")
        return total_minutes

    def _get_swimming_meters(self, user_id, response, sport_tab_index):
        METER_TOTAL_SELECTOR = 'tbody#%s-ytd > tr:nth-child(2) td:nth-child(2)' % sport_tab_index
        raw_meter = response.css(METER_TOTAL_SELECTOR).extract_first()
        raw_meter_numbers = re.findall(r'<td>(([0-9]*[,]?[0-9]*)) m</td>', raw_meter, re.M | re.I)[0][0]
        meter_total = float(raw_meter_numbers.replace(',', ''))
        self.logger.info(f"[Swimming] {user_id}: {meter_total}")
        return meter_total

    def _get_cycling_kilometers(self, user_id, response, sport_tab_index):
        KM_TOTAL_SELECTOR = 'tbody#%s-ytd > tr:nth-child(2) td:nth-child(2)' % sport_tab_index
        raw_km = response.css(KM_TOTAL_SELECTOR).extract_first()
        raw_km_numbers = re.findall(r'<td>(([0-9]*[,]?[0-9]*[.])?[0-9]+) km</td>', raw_km, re.M | re.I)[0][0]
        km_total = float(raw_km_numbers.replace(',', ''))
        self.logger.info(f"[Cycling] {user_id}: {km_total}")
        return km_total

    def _get_cycling_elevation(self, user_id, response, sport_tab_index):
        M_TOTAL_SELECTOR = 'tbody#%s-ytd > tr:nth-child(3) td:nth-child(2)' % sport_tab_index
        raw_meter = response.css(M_TOTAL_SELECTOR).extract_first()
        raw_meter_numbers = re.findall(r'<td>(([0-9]*[,]?[0-9]*)) m</td>', raw_meter, re.M | re.I)[0][0]
        meter_total = float(raw_meter_numbers.replace(',', ''))
        self.logger.info(f"[Cycling] elevation {user_id}: {meter_total}")
        return meter_total

    def _get_running_kilometers(self, user_id, response, sport_tab_index):
        KM_TOTAL_SELECTOR = 'tbody#%s-ytd > tr:nth-child(2) td:nth-child(2)' % sport_tab_index
        raw_km = response.css(KM_TOTAL_SELECTOR).extract_first()
        raw_km_numbers = re.findall(r'<td>(([0-9]*[,]?[0-9]*[.])?[0-9]+) km</td>', raw_km, re.M | re.I)[0][0]
        km_total = float(raw_km_numbers.replace(',', ''))
        self.logger.info(f"[Running] {user_id}: {km_total}")
        return km_total
