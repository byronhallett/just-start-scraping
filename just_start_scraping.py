# Built ins
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

__version__ = 'v1.1.0'


class Race:
    '''
    Holds data for each row of the race table, regardless of how soon it runs
    Is overwritten in mem each loop.
    '''
    def __init__(self, *, location, date, time,
                 runners=[], stars_present=False):
        self.location = location
        # Date comes from tz and clock
        self.date = date
        # Time comes from html
        self.time = time
        self.runners = runners[:]
        # Stars present is used to determine
        # if this race is ready to be exported
        self.stars_present = stars_present

    def add_runner(self, runner):
        self.runners.append(runner)

    def get_runners(self):
        return [run for run in self.runners if run.running]

    def __repr__(self):
        return "{} {}, stars: {}, horses: {}".format(
            self.time.strftime('%H:%M'),
            self.location,
            self.stars_present,
            len(self.runners))


class Runner:
    '''
    Individual column data for each horse row
    '''
    def __init__(self, *, name="", stars=0, mov1, min1, np, running):
        self.name = str(name).replace('*', '')
        self.stars = stars
        self.mov1 = mov1
        self.min1 = min1
        self.np = np
        # whether or not the horse is still in the race
        self.running = running

    def __repr__(self):
        return "{} {} {}".format(self.name,
                                 self.running,
                                 self.stars)


class JustStartSraping:
    '''
    Main class to handle loop and some variables.
    '''
    # Constants
    minute = 60
    idle_mins = minute * 20
    tz = pytz.timezone('Europe/London')
    login_url = "http://www.juststarthere.co.uk/user/login.html"
    user_field = "usr_login"
    pass_field = "usr_password"
    hidden_field = "op"
    hidden_value = "login"
    scrape_url = "http://www.juststarthere.co.uk/upcomingwinback.html"
    table_name = "racedata"
    race_info = "race_infoback"

    def __init__(self,
                 mov1_min=0.85,
                 mov1_times=("17:20", "20:55")):
        # Store parameters locally
        self.mov1_min = mov1_min  # threshold for the mov1 output
        self.mov1_times = (datetime.strptime(mov1_times[0], '%H:%M'),
                           datetime.strptime(mov1_times[1], '%H:%M'))
        next_race = None  # A variable to store the next upcoming race time

    def start(self):
        '''
        Called only when the script is started to initialise
        '''
        # Check output directory exists
        if not self.check_outdir():
            return False

        print("Starting scrape.")
        # get credentials and start session
        if not self.sign_in():
            # Credentials or connectivity
            print('sign_in_error')
            return False
        # Start main loop, and catch errors at this point
        self.safety_loop()

    def check_outdir(self):
        '''
        Ensures that the directory in the settings has been configured
        correctly
        '''
        test_dir = Settings.out_dir
        if not test_dir.exists():
            print("make sure the directory: '{}' exists".format(test_dir),
                  "or change the settings file")
            return False
        return True

    def sign_in(self):
        '''
        Prompts for user credentials and starts a new http session
        returns true if login was successful
        '''
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
        result = session.post(self.login_url,
                              data=self.login_data)
        self.session = session
        return True

    def re_sign_in(self):
        '''
        logs in again using credentials in memory
        If the server is not respondant, will refresh session entirely and try
        again.
        '''
        attempts = 0
        while True:
            try:
                self.session.post(self.login_url, data=self.login_data)
                return
            except requests.ConnectionError:
                attempts += 1
                print('server did not respond, trying again in 5 seconds. '
                      'number of attempts: {}'.format(attempts))
                # Cleaning old session
                self.session = requests.session()
                sleep(5)
                continue

    def safety_loop(self):
        '''
        A high level loop to print errors, but restart the scrape
        Will manually add safe errors to the exception tuple
        '''
        while True:
            try:
                self.scrape_loop()
            except (PermissionError, requests.ConnectionError,
                    requests.ConnectTimeout) as e:
                print(e)
                # A nominal time to wait for errors to be fixed
                sleep(15)

    def scrape_loop(self):
        '''
        This is the main loop which repeats after a variable amount of sleep
        Using the constants stored on this class, scrapes the race page,
        creates race and horse instances for each row,
        if no races exists, sleep for long time
        if races exists, sleeps until next one is due - 1 min
        '''
        while True:
            # Make sure still connected to session
            self.re_sign_in()

            print("Fetching data...")

            # Scrape the page
            current_races = self.get_races()

            # Waits if no races
            if current_races == []:
                print("No races, checking in {} minute(s)"
                      .format(self.idle_mins / 60))
                sleep(self.idle_mins)
                continue

            # Races with stars means that there is something to output
            starred_races = list(filter(lambda r: r.stars_present,
                                        current_races))

            if len(starred_races) > 0:
                print("new starred race(s) found, outputting to csv")
                self.output_races(starred_races)

            # need to check the other races for how long to sleep
            non_starred = list(filter(lambda r: r.stars_present is False,
                                      current_races))

            # Ensure that the only remaining races aren't all starred
            # That means that we sleep till tomorrow, since they should have
            # all been output
            if non_starred == []:
                # If they are,  sleep and move to next loop,
                # Current_races should be empty by then (no problem if not)
                print("No races further races, checking in {} minute(s)"
                      .format(self.idle_mins / 60))
                sleep(self.idle_mins)
                continue

            # Get the current server time based on timezone
            self.current_server_time = self.get_time()

            # calculate the time until the next race is due, and decide how
            # long to sleep
            self.next_race = min([
                (race.time - self.current_server_time).seconds
                for race in non_starred])
            if self.next_race < 60:
                next_wait = 0
            else:
                next_wait = min([self.next_race-59.9, self.idle_mins])
            print("Next race in {:.2f} minutes, waiting {:.2f} minutes"
                  .format(
                    self.next_race / 60,
                    next_wait / 60))
            sleep(next_wait)

    def get_races(self):
        '''
        Actual fetcha nd scrape of HTML. Creating of race and horse data
        returnsan array of current races.
        ...[race[horses], race[horses]]...
        '''
        result = self.session.get(
            self.scrape_url,
            headers=dict(referer=self.scrape_url)
        )
        page_data = BeautifulSoup(result.content, 'html.parser')
        # For debugging, use the data.html file
        # with open('data.html', 'r') as file:
        #     page_data = BeautifulSoup(file, 'html.parser')
        race_table = page_data.find(id=self.table_name)
        table_bodies = race_table.find_all('tbody')
        if len(table_bodies) == 0:
            return []
        print('Data loaded, analysing')
        races = []

        # Headers for easy index on horses rows
        min1_index = 15
        mov1_index = 16
        name_index = 0
        # Must break out of info text block, splitting on literal : "Horse ID:"
        name_split = "Horse ID:"
        np_index = 21
        star_index = 22
        runner_index = 1

        # Remeber which race wwe are currently adding to the result array
        # That allows use to store horses in the race by index
        # That way, races can be created first, then horses added
        race_index = -1

        # Scapre the table
        for table_body in table_bodies:
            table_rows = table_body.find_all('tr')

            # Break into each row
            for row in table_rows:

                # Logic if this row is a race header
                if self.is_race_info(row):
                    # Specifics about the table layout
                    info = row.td.text.split(',')
                    time_string, location = info[0].split(' ')[0:2]

                    # Create the race
                    this_race = Race(location=location,
                                     date=datetime.now(self.tz).date(),
                                     time=datetime.strptime(time_string,
                                                            '%H:%M'))
                    races.append(this_race)
                    race_index += 1
                    continue

                # Logic if this is a horse row
                if self.is_horse_info(row):

                    # Break the table row into columns
                    h_data = row.find_all('td')

                    # Place each column of interest in a variable for clarity
                    h_name = h_data[name_index].text.split(name_split)[0]
                    h_stars = h_data[star_index]
                    h_mov1 = float(h_data[mov1_index].string)
                    h_min1 = float(h_data[min1_index]
                                   .find_all('div')[0].string)
                    h_np = int(h_data[np_index].string)
                    h_run_td = h_data[runner_index].find_all('div')[1]['class']
                    star_count = self.stars_to_int(h_stars)

                    # If the current horse has a star, set the stars_present
                    # value on the race
                    if star_count > 0:
                        races[race_index].stars_present = True

                    # Some horses are listed, but are not going to run
                    h_running = "rt" not in h_run_td

                    # Use above information to create a horse object
                    this_runner = Runner(name=h_name, stars=star_count,
                                         mov1=h_mov1, min1=h_min1,
                                         np=h_np, running=h_running)

                    # Add horse to current race by index
                    races[race_index].add_runner(this_runner)
        return races

    def output_races(self, races):
        '''
        For a given array of races, appends information to a series of CSVs
        in the output folder.
        Each CSV has a number of constraints for horse selection
        - Number of stars
        - Newspaper tips
        - Mov1 value
        - Time of race
        '''
        for race in races:
            self.output_race(race)

    def output_race(self, race):

        # Ensure that this race has runners
        if race.get_runners() == []:
            return

        # A bool to check if the mov1 output should take place
        within_mov1_times = (
            race.time >= self.mov1_times[0] and
            race.time <= self.mov1_times
        )

        # A value needed to find the horse whose odds improved the most
        best_mov = self.best_mov1(race.get_runners())

        # Categories and requirements for each in a dictionary
        filtered_runners = {
            # Must have five stars
            'FIVESTARS.csv':
            list(filter(lambda h: h.stars == 5, race.get_runners())),
            # Must have no stars and np between 0 and 2
            'NOSTARS 0-2NP.csv':
            list(filter(lambda h: h.stars == 0 and
                        0 <= h.np <= 2,
                        race.get_runners())),
            # Must have 1 star
            'ONESTAR.csv':
            list(filter(lambda h: h.stars == 1,
                        race.get_runners())),
            # Must have 0 stars
            'NOSTARS.csv':
            list(filter(lambda h: h.stars == 0,
                        race.get_runners())),
            # Must be the most improved horse in the last minute and have
            # improved by at least mov1_min
            # Must also be between the correct times - will be an empty
            # list if not
            'MOV1.csv':
            [h for h in race.get_runners() if within_mov1_times and
             h.mov1 == best_mov and h.mov1 >= self.mov1_min]
        }

        # Iterate over each of the caterories above
        for sheet, runners in filtered_runners.items():
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
                                print("could not remove {}. It must be in use".format(
                                    str(outpath)))

            # now really write
            with outpath.open('a', newline='', encoding='utf8') as file:
                # Will not write anything if the list is empty
                for r in runners:
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
        '''
        Helper function to determine the best mov1 in a list of runners
        '''
        movs = [r.mov1 for r in runners]
        return max(movs)

    def is_race_info(self, row):
        '''
        Helper function to determine if this row matches the layout of a race
        '''
        try:
            return row.td['class'][0] == self.race_info
        except:
            return False

    def is_horse_info(self, row):
        '''
        Helper function to determine if this row matches the layout of a horse
        '''
        try:
            return 'runner' in row.find_all('td')[0]['class']
        except:
            return False

    def stars_to_int(self, stars):
        '''
        converts the filename of the star images into an int
        '''
        try:
            img = stars.img['src']
            name = img.replace('t.gif', '')
            # print(name)
            count = name.replace('/images/', '')
            # print(count)
            return int(count)
        except:
            return 0

    def get_time(self):
        '''
        Calculates the time on the JSH server using local time and timezone
        module
        '''
        return datetime.now(self.tz).replace(tzinfo=None)


if __name__ == "__main__":
    print("current version: {}".format(__version__))
    JustStartSraping().start()
