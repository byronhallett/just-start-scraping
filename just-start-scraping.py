from threading import Timer
from time import sleep, strptime
from bs4 import BeautifulSoup
import requests
import getpass


class Race:

    def __init__(self, *, location, time, runners, stars_present=False):
        self.location = location
        self.time = time
        self.runners = runners
        self.stars_present = stars_present


class Runner:
    def __init__(self, *, name, stars):
        self.name = name
        self.stars = stars


class JustStartSraping:

    # Constants
    minute = 60
    five_mins = minute * 5

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
        self.available_races = []
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
                password = "splinter"
        except:
            print("Bad credentials")
            return False
        session = requests.session()
        print("Session starting...")
        data = {
            self.user_field: user,
            self.pass_field: password,
            self.hidden_field: self.hidden_value
        }
        # print(data)
        # login_response = session.get(self.login_url)
        # tree = html.fromstring(login_response.text)
        result = session.post(self.login_url,
                              data=data)
        self.session = session
        print("Session running")
        return True

    def scrape_loop(self):
        while True:
            current_races = self.get_races()
            if current_races == []:
                print("No races, checking in {} minute(s)"
                      .format(self.five_mins / 60))
                sleep(self.five_mins)
                continue
            self.next_jump = min([race.time for race in current_races])
            next_jump_delay = (self.next_jump - self.get_time())
            next_wait = min([next_jump_delay, self.five_mins])
            print("Next jump in {} minutes, waiting {} minutes".format(
                next_jump_delay,
                next_wait))

    def get_races(self):
        # print(list(self.session.cookies))
        result = self.session.get(
            self.scrape_url,
            headers=dict(referer=self.scrape_url)
        )
        page_data = BeautifulSoup(result.content, 'html.parser')
        # TODO: Get the list of races and their relevant information
        race_table = page_data.find(id=self.table_name)
        return []
        races = []
        # for row in something
        stars_found = False
        race_runners = []
        # for row in something else
        this_name = "Test"
        this_stars = "5"
        stars_found = True
        this_runner = Runner(name=this_name, stars=this_stars)
        race_runners.append(this_runner)
        this_race = Race(location="Test",
                         time=strptime('4:42:25 AM', '%H:%M'),
                         runners=race_runners,
                         stars_present=stars_found)
        races.append(this_race)
        return races

    def get_time(self):
        time_page = requests.get(self.time_url)
        time_data = BeautifulSoup(time_page.content, 'html.parser')
        time_obj = strptime(time_data.find(id='t1').string, '%H:%M:%S %p')
        return time_obj


if __name__ == "__main__":
    import doctest
    doctest.testmod()
    JustStartSraping().start()
