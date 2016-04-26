from threading import Timer
from time import sleep
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import requests
import getpass


class Race:

    def __init__(self, *, location, time,
                 runners=[], stars_present=False):
        self.location = location
        self.time = time
        self.runners = runners[:]
        self.stars_present = stars_present

    def add_runner(self, runner):
        self.runners.append(runner)


class Runner:
    def __init__(self, *, name="", stars=0, mov1, np):
        self.name = name
        self.stars = stars
        self.mov1 = mov1
        self.np = np


class JustStartSraping:

    # Constants
    minute = 60
    idle_mins = minute * 10

    def __init__(self,
                 login_url="http://www.juststarthere.co.uk/user/login.html",
                 user_field="usr_login",
                 pass_field="usr_password",
                 hidden_field="op",
                 hidden_value="login",
                 scrape_url=("http://www.juststarthere" +
                             ".co.uk/upcomingraces.html"),
                 time_url="http://free.timeanddate.com/clock/i253rdyo/n136",
                 table_name="race_table"):
        self.login_url = login_url
        self.user_field = user_field
        self.pass_field = pass_field
        self.hidden_field = hidden_field
        self.hidden_value = hidden_value
        self.scrape_url = scrape_url
        self.time_url = time_url
        self.table_name = table_name

        # Page specific data
        self.scraped_races = []
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
            if user == "":
                user = "stephenjgray"
            password = getpass.getpass('enter password: ')
            if password == "":
                password = "***REMOVED***"
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
        print("Fetching data...")
        while True:
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
                output_races(starred_races)
            non_starred = list(filter(lambda r: r.stars_present is False,
                                      current_races))
            current_server_time = self.get_time()
            # print(current_server_time)
            self.next_jump = min([(race.time - current_server_time).seconds
                                  for race in non_starred])
            if self.next_jump < 60:
                next_wait = 0
            else:
                next_wait = min([self.next_jump-59, self.idle_mins])
            print("Next jump in {:.2f} minutes, waiting {:.2f} minutes".format(
                self.next_jump / 60,
                next_wait / 60))
            sleep(next_wait)
            # self.re_sign_in()

    def get_races(self):
        # print(list(self.session.cookies))
        result = self.session.get(
            self.scrape_url,
            headers=dict(referer=self.scrape_url)
        )
        page_data = BeautifulSoup(result.content, 'html.parser')
        race_table = page_data.find(id=self.table_name)
        table_body = race_table.tbody
        table_rows = table_body.find_all('tr')
        if len(table_body) == 0:
            return []
        print('Data loaded, analysing')
        races = []

        # Store last data for debugging
        with open('data.txt', 'w') as f:
            f.write(race_table)

        # print(race_table.thead)
        # print(race_table.thead.find_all('th'))
        # Headers for easy index on horses rows
        mov1_index = 18
        name_index = 21
        np_index = 23
        star_index = 24

        race_index = -1
        for row in table_rows:
            if self.is_race_info(row):
                race_index += 1
                info = row.td.string.split(',')
                time_string = info[2].replace(" ", "")
                this_race = Race(location=info[0:1],
                                 time=datetime.strptime(time_string, '%H:%M'))
                # if (last_race.time - datetime.now()).seconds < 0:
                #     last_race.time += timedelta(days=1)
                races.append(this_race)
                continue
            if self.is_horse_info(row):
                h_data = row.find_all('td')
                h_name = h_data[name_index]
                h_stars = h_data[star_index]
                h_mov1 = h_data[mov1_index]
                h_np = h_data[np_index]
                this_runner = Runner(name=h_name, stars=h_stars,
                                     mov1=h_mov1, np=h_np)
                races[race_index].add_runner(this_runner)
                try:
                    if int(h_stars) > 0:
                        races[race_index].stars_present = True
                except:
                    pass
                    # Nothing wrong, just no stars
        return races

    def output_races(self, races):
        for race in races:
            best_mov1 = max([runner.mov1 for runner in race.runners])
            # Save all categories
            sorted_runners = {
                'JSH FIVESTARS TBE.csv':
                list(filter(lambda r: r.stars == 5, race.runners)),
                'JSH NOSTARS TBE.csv':
                list(filter(lambda r: r.stars == 0 and 0 <= r.np <= 2,
                            race.runners)),
                'JSH MOV1 TBE.csv':
                list(filter(lambda r: r.stars == 0 and r.mov1 == best_mov1,
                            race.runners))
                }
            for sheet, runs in sorted_runners:
                with open(sheet, 'a') as file:
                    for r in runs:
                        csv_row = [datetime.now(),
                                   ":".join(race.time.hours,
                                            race.time.minutes),
                                   race.location,
                                   r.name]
                        file.write(csv_row)
                print('race: {}, {}:{}, added to CSVs'.format(
                    race.location, race.time.hours, race.time.minutes
                ))
            scraped_races.append(race)

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

    def get_time(self):
        time_page = requests.get(self.time_url)
        time_data = BeautifulSoup(time_page.content, 'html.parser')
        time_obj = datetime.strptime(time_data.find(id='t1').string,
                                     '%I:%M:%S %p')
        return time_obj


if __name__ == "__main__":
    import doctest
    doctest.testmod()
    JustStartSraping().start()
