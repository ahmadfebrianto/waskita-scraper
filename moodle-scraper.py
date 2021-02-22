import requests
import os
import urllib3
from bs4 import BeautifulSoup
from moodle_kit import Moodle
from getpass import getpass
from collections import defaultdict
from tabulate import tabulate
import concurrent.futures
from socket import gaierror
from urllib3.exceptions import NewConnectionError, MaxRetryError
from requests.exceptions import ConnectionError
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_request(url, headers):
    '''Perform GET HTTP request to the login page.'''

    response = requests.get(
        url,
        headers=headers,
        allow_redirects=True
    )

    return response


def get_course_urls(parsed_response):
    '''Retrieves each course's url and store them in a list.'''

    a = (parsed_response.find_all('a', class_="list-group-item", href=True))
    urls = [x.get('href') for x in a if 'course' in x.get('href')]
    return urls


class Course:
    '''Treat every course as an object.'''

    def __init__(self, course_name, section_items):
        self.course_name = course_name
        self.section_items = section_items

    def __repr__(self) -> str:
        return f'<{self.course_name}>'


def is_assignment(item_type):
    '''Check if an item is an assignement.'''

    if item_type.lower() == 'assignment':
        return True
    return False


def get_deadline(item_url, headers):
    '''Return the item's deadline only if it's an assignment'''

    get_response = BeautifulSoup(get_request(
        item_url, headers).text, 'html.parser')
    return get_response


def multithread(func, items):
    '''Run repeated processes with multithreading capability.'''

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        return executor.map(func, items)


def fetch_courses(course_urls, headers):
    '''Extract information about each course (name, sections, section items)'''

    def get_course_info(url):
        response = get_request(url, headers)
        if response.ok:
            parsed_response = BeautifulSoup(response.text, 'html.parser')

            # Get course name
            course_name = [x.strip()
                           for x in parsed_response.title.text.split('-')]
            course_name = f'[{course_name[0].split()[1]}]{course_name[1]} - {course_name[-1]}'

            # Get course's sections and store them in a list
            course_sections = parsed_response.select(
                '.content > .sectionname > span > a')
            course_sections = [x.string for x in course_sections]

            # Get the items of each section
            section_items = defaultdict(list)
            for i, section_name in enumerate(course_sections):
                items = parsed_response.select(
                    f'#section-{i}>div:nth-child(3)>ul:nth-child(4)>li>div>div>div:nth-child(2)>div>a')

                item_texts = [x.text.split() for x in items]
                item_names = [' '.join(x[:-1]) for x in item_texts]
                item_types = [x[-1] for x in item_texts]
                item_urls = [x.get('href') for x in items]

                for item_name, item_url, item_type in zip(item_names, item_urls, item_types):
                    deadline = ''
                    if is_assignment(item_type):
                        get_response = get_deadline(item_url, headers)
                        deadline = get_response.select_one(
                            '.submissionstatustable>div:nth-child(2)>table>tbody>tr:nth-child(4)>td').text
                        if 'submitted' in deadline:
                            deadline = 'SUBMITTED'
                    else:
                        deadline = 'NOT an assignment'
                    section_items[section_name].append(
                        [item_name, item_url, deadline])

            return Course(course_name, section_items)

    course_objects = multithread(get_course_info, course_urls)
    return course_objects


def format_section_name(name):
    '''Format each section's name that doesn't align to the common pattern.'''

    try:
        template = 'Pertemuan'
        if name != 'General' and template not in name:
            name = name.split('.')[0]
            return f'{template} {int(name)}'
        return name
    except:
        return name


def format_item_name(name):
    '''Split the item's long ugly name and return the longest one.'''

    try:
        name = list(map(lambda x: x.strip(), name.split('-')))
        return max(name, key=len)
    except:
        return name


def generate_summary(course_objects):
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
        recent_section = format_section_name(
            list(course.section_items.keys())[-1])

        section_items = ''
        deadline = ''

        items = list(course.section_items.values())[-1]
        for item_name, item_url, item_deadline in items:
            section_items += format_item_name(item_name) + \
                '\n' + item_url + '\n\n'
            deadline += item_deadline + '\n\n\n'

        return [id, name, recent_section, section_items, deadline]

    tables = multithread(unpack_course, course_objects)
    return tabulate(tables, headers=headers, tablefmt=table_format, colalign=('left', 'left', 'left', 'left'))


def print_error_message(messages=[]):
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

        moodle = Moodle()
        response = moodle.login(login_url, username, password)
        headers = response.request.headers

        soup = BeautifulSoup(response.text, 'html.parser')
        today = soup.find(
            'td', class_='today').a.get('aria-label')
        print(today)

        # Course urls extraction after the successful login
        course_urls = get_course_urls(soup)
        course_objects = fetch_courses(course_urls, headers)

        # Print summary table
        print()
        print(generate_summary(course_objects))
        print()

        # Logout
        moodle.logout()
        exit()

    except (gaierror, NewConnectionError, MaxRetryError, ConnectionError) as e:
        print_error_message([
            '[!] A connection error occured! It might be your slow bandwidth.',
            '[!] Fix your connection and try again!'])

    except KeyboardInterrupt as e:
        print_error_message(['[-] Program was interrupted!'])

    except Exception as e:
        print_error_message([e.__str__()])


if __name__ == "__main__":
    main()
