import os
import re
from time import sleep

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright
from tinydb import TinyDB, Query
from tinydb.database import Table

# Load environment variables from .env file
load_dotenv()


class StravaScraper:
    BASE_URL = 'https://www.strava.com'

    def __init__(self, club_id: str, year: int = 2024):
        self.club_id = club_id
        self.year = year
        self.db: Table = TinyDB(f"./db/strava-leaderboard-{year}-{club_id}.json")
        self.leaderboard = Query()

        # Get credentials from environment variables
        self.email = os.getenv("STRAVA_EMAIL")
        self.password = os.getenv("STRAVA_PASSWORD")

        if not self.email or not self.password:
            raise ValueError("STRAVA_EMAIL and STRAVA_PASSWORD must be set in .env file")

    def login(self, page: Page) -> None:
        """Login to Strava"""
        print(f'Visiting {self.BASE_URL}/login...')
        page.goto(f"{self.BASE_URL}/login")

        # Accept cookies if present
        try:
            page.get_by_role("button", name="Accept All").click(timeout=3000)
        except:
            pass

        # Fill in login form
        page.get_by_role("textbox", name="Email").fill(self.email)
        page.get_by_role("button", name="Log In").click()
        sleep(3)

        # Use password instead
        try:
            page.get_by_role("button", name="Use password instead").click(timeout=3000)
            sleep(2)
            page.get_by_role("textbox", name="Password").fill(self.password)
            sleep(2)
            page.get_by_role("button", name="Log in").click()
        except:
            # Password field might be already visible
            page.get_by_role("textbox", name="Password").fill(self.password)
            page.get_by_role("button", name="Log in").click()

        # Wait for login to complete
        page.wait_for_load_state("networkidle")
        print('Logged in...')

    def scrape_club_members(self, page: Page) -> None:
        """Scrape all club members across all pages"""
        current_page = 1

        while True:
            club_url = f"{self.BASE_URL}/clubs/{self.club_id}/members?page={current_page}"
            print(f"Scraping page {current_page}: {club_url}")
            page.goto(club_url)
            page.wait_for_load_state("networkidle")

            # Get all member links
            member_links = page.locator('div.border-top > ul.list-athletes > li > div.text-headline a')
            count = member_links.count()

            if count == 0:
                print("No more members found")
                break

            # Extract member data
            for i in range(count):
                try:
                    link = member_links.nth(i)
                    profile_path = link.get_attribute('href')
                    user_name = link.inner_text()
                    profile_url = self.BASE_URL + profile_path

                    user_id_match = re.findall(r'athletes/(\d+)', profile_url, re.M | re.I)
                    if user_id_match:
                        user_id = user_id_match[0]
                        self.db.upsert(
                            {'user_id': user_id, 'name': user_name, 'profile_url': profile_url},
                            self.leaderboard.user_id == user_id
                        )
                        print(f"Found member: {user_name} (ID: {user_id})")

                        # Open profile in new tab
                        context = page.context
                        new_page = context.new_page()

                        try:
                            # Scrape profile data in new tab
                            self.scrape_profile(new_page, user_id, profile_url)
                        finally:
                            # Close the new tab
                            new_page.close()

                except Exception as e:
                    print(f"Error processing member {i}: {e}")
                    continue

            # Check if there's a next page
            next_page_button = page.locator('nav > ul.pagination > li.next_page > a')
            if next_page_button.count() == 0:
                print("No more pages")
                break

            current_page += 1

    def scrape_profile(self, page: Page, user_id: str, profile_url: str) -> None:
        """Scrape profile data for a specific user"""

        print(f"Scraping page: {profile_url}")
        page.goto(profile_url)
        page.wait_for_load_state("networkidle")

        # Check if account is private
        try:
            private_message = page.get_by_text("This Account Is Private")
            if private_message.count() > 0:
                if page.get_by_role("button", name="Request to Follow").count() > 0:
                    page.get_by_role("button", name="Request to Follow").click(timeout=2000)
                print(f"User {user_id} has a private account - skipping • 👤 follow requested")
                self.db.upsert(
                    {'profile_is_private': True},
                    self.leaderboard.user_id == user_id
                )
                return
        except:
            pass

        # Account is public, continue with scraping
        page.locator("#ytd_year_sport-0 div").filter(has_text=re.compile(r"^2025$")).click()
        page.wait_for_load_state("networkidle")

        print("before scraping data")
        # Get sport data
        running_data = self._get_sport_data(page, 'Run')
        cycling_data = self._get_sport_data(page, 'Ride')
        swimming_data = self._get_sport_data(page, 'Swim')

        # Update database
        self.db.upsert({
            'profile_is_private': False,
            'cycling_distance_in_km': cycling_data['distance'],
            'cycling_duration_in_minute': cycling_data['duration'],
            'cycling_elevation_in_meter': cycling_data['elevation'],
            'running_distance_in_km': running_data['distance'],
            'running_duration_in_minute': running_data['duration'],
            'running_elevation_in_meter': running_data['elevation'],
            'swimming_distance_in_meter': swimming_data['distance'],
            'swimming_duration_in_minute': swimming_data['duration']
        }, self.leaderboard.user_id == user_id)

        print(f"Completed profile for user {user_id}")

    def _get_sport_tab_index(self, page: Page, sport_activity: str) -> str | None:
        """Get the CSS sport tab index for a specific sport"""
        try:
            button = page.locator(f'button.selected[title="{sport_activity}"]')
            if button.count() == 0:
                return None

            css_classes = button.get_attribute('class')
            pattern = r'sport-\d+-tab'
            matches = re.findall(pattern, css_classes)

            if matches:
                sport_index = matches[0].replace('-tab', '')
                print(f"Found sport index {sport_index} for {sport_activity}")
                return sport_index
            return None
        except Exception as e:
            print(f"Error finding sport tab for {sport_activity}: {e}")
            return None

    def _get_sport_data(self, page: Page, sport_name: str) -> dict:
        """Extract distance, duration, and elevation for a sport"""
        sport_index = self._get_sport_tab_index(page, sport_name)

        if not sport_index:
            return {'distance': 0, 'duration': 0, 'elevation': 0}

        data = {'distance': 0, 'duration': 0, 'elevation': 0}

        try:
            tbody = page.locator(f'tbody#{sport_index}-ytd')

            # Get distance (row 2)
            distance_cell = tbody.locator('tr:nth-child(2) td:nth-child(2)')
            distance_text = distance_cell.inner_text()

            if 'km' in distance_text:
                km_match = re.findall(r'([\d,\.]+)\s*km', distance_text)
                if km_match:
                    data['distance'] = float(km_match[0].replace(',', ''))
            elif 'm' in distance_text:
                m_match = re.findall(r'([\d,\.]+)\s*m', distance_text)
                if m_match:
                    data['distance'] = float(m_match[0].replace(',', ''))

            # Get duration (row 3 for running/swimming, row 4 for cycling)
            duration_row = 3 if sport_name in ['Run', 'Swim'] else 4
            duration_cell = tbody.locator(f'tr:nth-child({duration_row}) td:nth-child(2)')
            duration_text = duration_cell.inner_text()

            time_match = re.findall(r'(\d+)h\s*(\d+)m', duration_text)
            if time_match:
                hours, minutes = time_match[0]
                data['duration'] = int(hours) * 60 + int(minutes)

            # Get elevation (row 4 for running, row 3 for cycling)
            if sport_name != 'Swim':
                elevation_row = 4 if sport_name == 'Run' else 3
                elevation_cell = tbody.locator(f'tr:nth-child({elevation_row}) td:nth-child(2)')
                elevation_text = elevation_cell.inner_text()

                elevation_match = re.findall(r'([\d,]+)\s*m', elevation_text)
                if elevation_match:
                    data['elevation'] = float(elevation_match[0].replace(',', ''))

            print(f"[{sport_name}] Distance: {data['distance']}, Duration: {data['duration']}min, Elevation: {data['elevation']}m")

        except Exception as e:
            print(f"Error extracting {sport_name} data: {e}")

        return data

    def run(self) -> None:
        """Main execution method"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            try:
                # Login
                self.login(page)

                # Scrape all members
                self.scrape_club_members(page)

                print("Scraping completed!")

            except Exception as e:
                print(f"Error during scraping: {e}")
            finally:
                context.close()
                browser.close()


# Example usage in main.py:
if __name__ == "__main__":
    CLUB_ID = "1206518"
    YEAR = 2025

    scraper = StravaScraper(club_id=CLUB_ID, year=YEAR)
    scraper.run()

