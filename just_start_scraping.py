from time import sleep
from datetime import datetime, timedelta
from pathlib import Path
import getpass
import csv
# Extras
import pytz
import requests
from bs4 import BeautifulSoup
# this app
from setup import *


class Race:

    def __init__(self, *, location, date, time,
                 runners=[], stars_present=False):
        self.location = location
        self.date = date
        self.time = time
        self.runners = runners[:]
        self.stars_present = stars_present

    def add_runner(self, runner):
        self.runners.append(runner)

    def get_runners(self):
        return [run for run in self.runners if run.running]


class Runner:
    def __init__(self, *, name="", stars=0, mov1, min1, np, running):
        self.name = str(name).replace('*', '')
        self.stars = stars
        self.mov1 = mov1
        self.min1 = min1
        self.np = np
        self.running = running


class JustStartSraping:

    # Constants
    minute = 60
    idle_mins = minute * 20
    tz = pytz.timezone('Europe/London')

    def __init__(self,
                 login_url="http://www.juststarthere.co.uk/user/login.html",
                 user_field="usr_login",
                 pass_field="usr_password",
                 hidden_field="op",
                 hidden_value="login",
                 scrape_url=("http://www.juststarthere" +
                             ".co.uk/upcomingraces.html"),
                 time_url="http://free.timeanddate.com/clock/i253rdyo/n136",
                 table_name="race_table",
                 mov1_min=0.85,
                 min1_range=[10.5, 75]):
        self.login_url = login_url
        self.user_field = user_field
        self.pass_field = pass_field
        self.hidden_field = hidden_field
        self.hidden_value = hidden_value
        self.scrape_url = scrape_url
        self.time_url = time_url
        self.table_name = table_name
        self.mov1_min = mov1_min

        # Page specific data
        self.next_jump = None

    def start(self):
        print("Starting scrape.")
        if not self.sign_in():
            print('sign_in_error')
            return False
        self.scrape_loop()

    def sign_in(self):
        try:
            user = input('enter username: ')
            password = input('enter password: ')
        except:
            print("Bad credentials")
            return False
        session = requests.session()
        print("Session starting...")
        self.login_data = {
            self.user_field: user,
            self.pass_field: password,
            self.hidden_field: self.hidden_value
        }
        # print(data)
        # login_response = session.get(self.login_url)
        # tree = html.fromstring(login_response.text)
        result = session.post(self.login_url,
                              data=self.login_data)
        self.session = session
        return True

    def re_sign_in(self):
        self.session.post(self.login_url, data=self.login_data)

    def scrape_loop(self):
        while True:
            self.re_sign_in()
            print("Fetching data...")
            current_races = self.get_races()
            if current_races == []:
                print("No races, checking in {} minute(s)"
                      .format(self.idle_mins / 60))
                sleep(self.idle_mins)
                # self.re_sign_in()
                continue
            # print(list(len(rac.runners) for rac in current_races))
            starred_races = list(filter(lambda r: r.stars_present,
                                        current_races))
            if len(starred_races) > 0:
                print("new starred race(s) found, outputting to csv")
                self.output_races(starred_races)
            non_starred = list(filter(lambda r: r.stars_present is False,
                                      current_races))
            self.current_server_time = self.get_time()
            # Ensure that the only remaining races aren't all starred
            if non_starred == []:
                # If they are,  sleep and move to next loop,
                # Current_races should be empty by then (no problem if not)
                print("No races further races, checking in {} minute(s)"
                      .format(self.idle_mins / 60))
                sleep(self.idle_mins)
                continue
            self.next_jump = min([(
                race.time - self.current_server_time).seconds
                                  for race in non_starred])
            if self.next_jump < 60:
                next_wait = 0
            else:
                next_wait = min([self.next_jump-59.9, self.idle_mins])
            print("Next race in {:.2f} minutes, waiting {:.2f} minutes"
                  .format(
                    self.next_jump / 60,
                    next_wait / 60))
            sleep(next_wait)

    def get_races(self):
        # print(list(self.session.cookies))
        result = self.session.get(
            self.scrape_url,
            headers=dict(referer=self.scrape_url)
        )
        page_data = BeautifulSoup(result.content, 'html.parser')
        # file = open('data.txt','r')
        # page_data = BeautifulSoup(file, 'html.parser')
        # file.close()
        race_table = page_data.find(id=self.table_name)
        table_body = race_table.tbody
        table_rows = table_body.find_all('tr')
        if len(table_body) == 0:
            return []
        print('Data loaded, analysing')
        races = []

        # Store last data for debugging
        # with open('data.txt', 'w') as f:
        #     f.write(race_table.prettify())

        # print(race_table.thead)
        # print(race_table.thead.find_all('th'))
        # Headers for easy index on horses rows
        min1_index = 17
        mov1_index = 18
        name_index = 21
        np_index = 23
        star_index = 24
        runner_index = 3

        race_index = -1
        for row in table_rows:
            if self.is_race_info(row):
                race_index += 1
                info = row.td.string.split(',')
                # print(info)
                time_string = info[2].replace(" ", "")
                this_race = Race(location=info[1][1:],
                                 date=datetime.now(self.tz).date(),
                                 time=datetime.strptime(time_string, '%H:%M'))
                # if (last_race.time - datetime.now()).seconds < 0:
                #     last_race.time += timedelta(days=1)
                races.append(this_race)
                continue
            if self.is_horse_info(row):
                h_data = row.find_all('td')
                h_name = h_data[name_index].string
                h_stars = h_data[star_index]
                h_mov1 = float(h_data[mov1_index].string)
                h_min1 = float(h_data[min1_index].find_all('div')[0].string)
                h_np = int(h_data[np_index].string)
                h_run_td = h_data[runner_index].find_all('div')[0]['class']
                star_count = self.stars_to_int(h_stars)
                if star_count > 0:
                    races[race_index].stars_present = True
                h_running = True
                if "non-runner" in h_run_td:
                    h_running = False
                this_runner = Runner(name=h_name, stars=star_count,
                                     mov1=h_mov1, min1=h_min1,
                                     np=h_np, running=h_running)
                races[race_index].add_runner(this_runner)
        return races

    def output_races(self, races):
        
        for race in races:
            best_mov = self.best_mov1(race.get_runners())
            # Save all categories
            sorted_runners = {
                'FIVESTARS.csv':
                list(filter(lambda r: r.stars == 5, race.get_runners())),
                'NOSTARS 0-2NP.csv':
                list(filter(lambda r: r.stars == 0 and
                            0 <= r.np <= 2,
                            race.get_runners())),
                'ONESTAR.csv':
                list(filter(lambda r: r.stars == 1,
                            race.get_runners())),
                'NOSTARS.csv':
                list(filter(lambda r: r.stars == 0,
                            race.get_runners())),
                'MOV1.csv':
                list(filter(lambda r: r.mov1 == best_mov and
                            r.mov1 >= self.mov1_min,
                            race.get_runners()))
                }            
            for sheet, runs in sorted_runners.items():
                outpath = Settings.out_dir / sheet
                # Check the output file to make sure the
                # date hasn't changes since the last row was written
                if outpath.exists():
                    with outpath.open('r', newline='', encoding='utf8') as file:
                        lines = file.readlines()
                        if len(lines) > 0:
                            first_date = lines[-1].split(',')[0]
                            current_date = race.date.strftime("%d/%m/%y")
                            if first_date != current_date:
                                # Must be the next day
                                # Close file to avoid permission errors
                                file.close()
                                try:
                                    outpath.unlink()
                                except:
                                    print('could not remove {}. It must be in use'.format(
                                        str(outpath)))
                # now really write
                with outpath.open('a', newline='', encoding='utf8') as file:
                    for r in runs:
                        csv_writer = csv.writer(file)
                        csv_writer.writerow(
                            [race.date.strftime("%d/%m/%y"),
                             race.time.strftime("%H:%M"),
                             race.location,
                             r.name])
            print('race: {}, {}:{}, added to CSVs'.format(
                race.location, race.time.hour, race.time.minute
            ))

    def best_mov1(self, runners):
        movs = [r.mov1 for r in runners]
        return max(movs)

    def is_race_info(self, row):
        try:
            return row.td['class'][0] == 'h_race_info'
        except:
            return False

    def is_horse_info(self, row):
        try:
            return 'runner' in row.find_all('td')[2]['class']
        except:
            return False

    def stars_to_int(self, stars):
        try:
            img = stars.img['src']
            name = img.replace('.gif', '')
            # print(name)
            count = name.replace('/beta/images/rank/', '')
            # print(count)
            return int(count)
        except:
            return 0

    def get_time(self):
        time_page = requests.get(self.time_url)
        time_data = BeautifulSoup(time_page.content, 'html.parser')
        time_obj = datetime.strptime(time_data.find(id='t1').string,
                                     '%I:%M:%S %p')
        return time_obj


if __name__ == "__main__":
    # import doctest
    # doctest.testmod()
    JustStartSraping().start()
