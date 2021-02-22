from urllib3 import disable_warnings
from urllib3.exceptions import NewConnectionError, MaxRetryError, InsecureRequestWarning
from requests.exceptions import ConnectionError
from socket import gaierror
from bs4 import BeautifulSoup
from moodle_kit import Moodle
from getpass import getpass
from collections import defaultdict
from tabulate import tabulate
import requests
import os
import concurrent.futures
disable_warnings(InsecureRequestWarning)


class Course:
    '''Treat every course as an object.'''

    def __init__(self, course_name, section_items):
        self.course_name = course_name
        self.section_items = section_items

    def __repr__(self) -> str:
        return f'<{self.course_name}>'


class MyMoodle(Moodle):

    def __init__(self) -> None:
        super().__init__()

    def get_request(self, url):
        '''Perform GET HTTP request to the login page.'''

        response = requests.get(
            url,
            headers=self.request_headers,
            allow_redirects=True
        )
        return response

    def get_course_urls(self, soup):
        '''Retrieves each course's url and store them in a list.'''

        a_tags = (soup.find_all('a', class_="list-group-item", href=True))
        urls = [x.get('href') for x in a_tags if 'course' in x.get('href')]
        return urls

    def is_assignment(self, item_type):
        '''Check if an item is an assignement.'''

        if item_type.lower() == 'assignment':
            return True
        return False

    def get_deadline(self, item_url):
        '''Return the item's deadline only if it's an assignment'''

        soup = BeautifulSoup(self.get_request(
            item_url).text, 'html.parser')
        return soup

    def multithread(self, func, items):
        '''Run repeated processes with multithreading capability.'''

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            return executor.map(func, items)

    def fetch_courses(self, course_urls):
        '''Extract information about each course (name, sections, section items)'''

        def get_course_info(url):
            response = self.get_request(url)
            if response.ok:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Get course name
                course_name = [x.strip()
                               for x in soup.title.text.split('-')]
                course_name = f'[{course_name[0].split()[1]}]{course_name[1]} - {course_name[-1]}'

                # Get course's sections and store them in a list
                course_sections = soup.select(
                    '.content > .sectionname > span > a')
                course_sections = [x.string for x in course_sections]

                # Get the items of each section
                section_items = defaultdict(list)
                for i, section_name in enumerate(course_sections):
                    items = soup.select(
                        f'#section-{i}>div:nth-child(3)>ul:nth-child(4)>li>div>div>div:nth-child(2)>div>a')

                    item_texts = [x.text.split() for x in items]
                    item_names = [' '.join(x[:-1]) for x in item_texts]
                    item_types = [x[-1] for x in item_texts]
                    item_urls = [x.get('href') for x in items]

                    for item_name, item_url, item_type in zip(item_names, item_urls, item_types):
                        deadline = ''
                        if self.is_assignment(item_type):
                            get_response = self.get_deadline(item_url)
                            deadline = get_response.select_one(
                                '.submissionstatustable>div:nth-child(2)>table>tbody>tr:nth-child(4)>td').text
                            if 'submitted' in deadline:
                                deadline = 'SUBMITTED'
                        else:
                            deadline = 'NOT an assignment'
                        section_items[section_name].append(
                            [item_name, item_url, deadline])

                return Course(course_name, section_items)

        course_objects = self.multithread(get_course_info, course_urls)
        return course_objects

    def format_section_name(self, name):
        '''Format each section's name that doesn't align to the common pattern.'''

        try:
            template = 'Pertemuan'
            if name != 'General' and template not in name:
                name = name.split('.')[0]
                return f'{template} {int(name)}'
            return name
        except:
            return name

    def format_item_name(self, name):
        '''Split the item's long ugly name and return the longest word.'''

        try:
            name = list(map(lambda x: x.strip(), name.split('-')))
            return max(name, key=len)
        except:
            return name

    def generate_summary(self, course_objects):
        '''Put everything together in a nicely formatted table.'''

        headers = ['ID', 'Course Name', 'Recent Section',
                   'Section Items', 'Deadline']
        table_format = 'fancy_grid'

        def unpack_course(course):
            # Course ID
            id = course.course_name[:7][1:-1]

            # Course name
            name = course.course_name[7:]

            # Section name
            recent_section = self.format_section_name(
                list(course.section_items.keys())[-1])

            section_items = ''
            deadline = ''

            items = list(course.section_items.values())[-1]
            for item_name, item_url, item_deadline in items:
                section_items += self.format_item_name(item_name) + \
                    '\n' + item_url + '\n\n'
                deadline += item_deadline + '\n\n\n'

            return [id, name, recent_section, section_items, deadline]

        tables = self.multithread(unpack_course, course_objects)
        return tabulate(tables, headers=headers, tablefmt=table_format, colalign=('left', 'left', 'left', 'left'))

    def print_error_message(self, messages=[]):
        '''Print coustomized error messages.'''

        if isinstance(messages, str):
            messages = [messages]
        if len(messages) > 1:
            print()
            for message in messages:
                print(f'[!] {message}')
        else:
            print(f'\n\n[!] {messages[0]}')
        exit('\n[!] Program exited.\n')


def main():

    login_url = os.getenv("wskt_login")
    username = os.getenv("wskt_user")
    password = os.getenv("wskt_pass")

    try:
        print()
        while not login_url:
            login_url = input('[!] Login Page URL\t= ')

        while not username:
            username = input('[!] Username\t\t= ')

        while not password:
            password = getpass('[!] Password\t\t= ')

        moodle = MyMoodle()
        moodle.login(login_url, username, password)

        soup = BeautifulSoup(moodle.response.text, 'html.parser')
        today = soup.find(
            'td', class_='today').a.get('aria-label')
        print(today)

        # Course urls extraction after the successful login
        course_urls = moodle.get_course_urls(soup)
        course_objects = moodle.fetch_courses(course_urls)

        # Print summary table
        print()
        print(moodle.generate_summary(course_objects))
        print()

        moodle.logout()
        exit()

    except (gaierror, NewConnectionError, MaxRetryError, ConnectionError) as e:
        moodle.print_error_message([
            '[!] A connection error occured! It might be your slow bandwidth.',
            '[!] Fix your connection and try again!'])

    except KeyboardInterrupt as e:
        moodle.print_error_message(['[-] Program was interrupted!'])

    except Exception as e:
        moodle.print_error_message([e.__str__()])


if __name__ == "__main__":
    main()
