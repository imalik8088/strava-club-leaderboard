# -*- coding: utf-8 -*-
from .credentials import strava
import re

import scrapy
from scrapy.http import FormRequest
from tinydb import TinyDB, Query
from tinydb.database import Table


class StravaSpider(scrapy.Spider):
    BASE_URL = 'https://www.strava.com'
    name = 'strava'
    allowed_domains = ['strava.com']
    start_urls = ['https://www.strava.com/login']
    cookies = {}
    db: Table = TinyDB('./db/strava-leaderboard.json')
    Leaderboard = Query()
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

    def after_login(self, response):
        cookie = response.headers.getlist('Set-Cookie')[0].decode("utf-8").split(';')[0]
        self.cookies = dict(cookie.split("=") for x in cookie.split(";"))
        self.logger.info(f"[Cookie] {self.cookies}")
        self.logger.info('Logged in... ')

        club_url = 'https://www.strava.com/clubs/285486/members'
        yield scrapy.Request(url=club_url, callback=self.club_member_overview)


    def club_member_overview(self, response):
        MEMBER_SELECTOR = 'div.border-top > ul.list-athletes > li > div.text-headline'
        for list_user_block in response.css(MEMBER_SELECTOR):
            profile_url = self.BASE_URL + list_user_block.css("a::attr(href)").extract_first()
            comparision_data_url = profile_url + "/profile_sidebar_comparison?hl=en-US&ytd_year=2020"
            user_name = list_user_block.css("a::text").extract_first()

            user_id = re.findall(r'athletes/(\d*)', profile_url, re.M | re.I)[0]
            self.db.upsert({'user_id': user_id, 'name': user_name, 'profile_url': profile_url}, self.Leaderboard.user_id == user_id)

            yield scrapy.Request(url=comparision_data_url,
                                 headers=self.headers,
                                 cookies=self.cookies,
                                 callback=self.profile_crawler)

    def profile_crawler(self, response):
        user_id = re.findall(r'athletes/(\d*)', response.request.url, re.M | re.I)[0]

        cycling_kilometers = self._get_cycling_kilometers(user_id, response)
        cycling_minutes = self._get_cycling_hours(user_id, response)
        running_kilometers = self._get_running_kilometers(user_id, response)
        running_minutes = self._get_running_hours(user_id, response)
        swimming_meters = self._get_swimming_meters(user_id, response)
        swimming_miutes = self._get_swimming_hours(user_id, response)

        self.db.upsert({
            'cyclingDistanceInKm': cycling_kilometers,
            'cyclingDurationInMinute': cycling_minutes,
            'runningDistanceInKm': running_kilometers,
            'runningDurationInMinute': running_minutes,
            'swimmingDistanceInMeter': swimming_meters,
            'swimmingDurationInMinute': swimming_miutes
        }, self.Leaderboard.user_id == user_id)

        self.logger.info('Done.')

    def _get_swimming_hours(self, user_id, response):
        CYCLING_HOURS_TOTAL_SELECTOR = "#swimming-ytd > tr:nth-child(2) > td:nth-child(2)"
        raw_time = response.css(CYCLING_HOURS_TOTAL_SELECTOR).extract_first()
        hours_and_minutes = re.findall(r'(\d{1,})', raw_time, re.M | re.I)
        minutes_from_hours = int(hours_and_minutes[0]) * 60
        minutes = int(hours_and_minutes[1])
        total_minutes = minutes_from_hours + minutes
        self.logger.info(f"[Cycling] {hours_and_minutes[0]} hours and {hours_and_minutes[1]} minutes")
        return total_minutes

    def _get_cycling_hours(self, user_id, response):
        CYCLING_HOURS_TOTAL_SELECTOR = "#cycling-ytd > tr:nth-child(2) > td:nth-child(2)"
        raw_time = response.css(CYCLING_HOURS_TOTAL_SELECTOR).extract_first()
        hours_and_minutes = re.findall(r'(\d{1,})', raw_time, re.M | re.I)
        minutes_from_hours = int(hours_and_minutes[0]) * 60
        minutes = int(hours_and_minutes[1])
        total_minutes = minutes_from_hours + minutes
        self.logger.info(f"[Cycling] {hours_and_minutes[0]} hours and {hours_and_minutes[1]} minutes")
        return total_minutes

    def _get_running_hours(self, user_id, response):
        CYCLING_HOURS_TOTAL_SELECTOR = "#running-ytd > tr:nth-child(2) > td:nth-child(2)"
        raw_time = response.css(CYCLING_HOURS_TOTAL_SELECTOR).extract_first()
        hours_and_minutes = re.findall(r'(\d{1,})', raw_time, re.M | re.I)
        minutes_from_hours = int(hours_and_minutes[0]) * 60
        minutes = int(hours_and_minutes[1])
        total_minutes = minutes_from_hours + minutes
        self.logger.info(f"[Running] {hours_and_minutes[0]} hours and {hours_and_minutes[1]} minutes")
        return total_minutes

    def _get_swimming_meters(self, user_id, response):
        CYCLING_KM_TOTAL_SELECTOR = '#swimming-ytd > tr:nth-child(1) > td:nth-child(2)'
        raw_meter = response.css(CYCLING_KM_TOTAL_SELECTOR).extract_first()
        raw_meter_numbers = re.findall(r'<td>(([0-9]*[,]?[0-9]*)) m</td>', raw_meter, re.M | re.I)[0][0]
        meter_total = float(raw_meter_numbers.replace(',', ''))
        self.logger.info(f"[Cycling] {user_id}: {meter_total}")
        return meter_total

    def _get_cycling_kilometers(self, user_id, response):
        CYCLING_KM_TOTAL_SELECTOR = '#cycling-ytd > tr:nth-child(1) > td:nth-child(2)'
        raw_km = response.css(CYCLING_KM_TOTAL_SELECTOR).extract_first()
        raw_km_numbers = re.findall(r'<td>(([0-9]*[,]?[0-9]*[.])?[0-9]+) km</td>', raw_km, re.M | re.I)[0][0]
        km_total = float(raw_km_numbers.replace(',', ''))
        self.logger.info(f"[Cycling] {user_id}: {km_total}")
        return km_total

    def _get_running_kilometers(self, user_id, response):
        CYCLING_KM_TOTAL_SELECTOR = '#running-ytd > tr:nth-child(1) > td:nth-child(2)'
        raw_km = response.css(CYCLING_KM_TOTAL_SELECTOR).extract_first()
        raw_km_numbers = re.findall(r'<td>(([0-9]*[,]?[0-9]*[.])?[0-9]+) km</td>', raw_km, re.M | re.I)[0][0]
        km_total = float(raw_km_numbers.replace(',', ''))
        self.logger.info(f"[Running] {user_id}: {km_total}")
        return km_total
