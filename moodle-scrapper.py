import requests
import urllib3
from bs4 import BeautifulSoup
from getpass import getpass
from time import time, sleep
from collections import defaultdict
from tabulate import tabulate
import itertools
import sys
import threading
import concurrent.futures

from socket import gaierror
from urllib3.exceptions import NewConnectionError, MaxRetryError
from requests.exceptions import ConnectionError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_request(url, headers, login_page=False):
    '''
    Perform GET HTTP request to the login page.
    '''

    response = requests.get(
        url,
        headers=headers,
        allow_redirects=True
    )

    if login_page:
        # Obtain logintoken from the initial GET request to login page
        login_token = BeautifulSoup(response.text, 'html.parser').select_one(
            '#login > input:nth-child(3)').get('value')
        return response, login_token

    return response


def post_request(url, headers, login_token, username, password):
    '''
    Performs POST HTTP request to submit the login form with the given credentials.
    '''

    response = requests.post(url,
                             headers=headers,
                             data={
                                 'anchor': '',
                                 'logintoken': login_token,
                                 'username': username,
                                 'password': password
                             },
                             allow_redirects=True
                             )

    return response


def attempt_login(login_url, headers, username, password):
    '''
    Performs the login process starting from GET to POST request sequentially.
    '''

    # Obtain logintoken and MoodleSession
    response, logintoken = get_request(login_url, headers, login_page=True)

    # Append MoodleSession obtained to the headers
    headers['Cookie'] = "MoodleSession=" + \
        response.cookies.get('MoodleSession')

    # Attempt login with logintoken and new headers
    post_request_response = post_request(
        login_url, headers, logintoken, username, password)
    parsed_response = BeautifulSoup(post_request_response.text, 'html.parser')

    if parsed_response.title.text == 'Dashboard':
        print(f'\n[*] Login successful!')

        # Obtain new MoodleSession after successful login
        new_moodle_session = post_request_response.request.headers.get(
            'Cookie').split('=')[1]

        # Update MoodleSesson value in the headers
        headers['Cookie'] = 'MoodleSession=' + new_moodle_session

        return parsed_response, headers

    else:
        print(f'\n[!] Login failed!')
        print(f'[!] {post_request_response.status_code}')
        print(f'\n[!] Program exited.')
        print()
        exit()


def get_course_urls(parsed_response):
    '''
    Retrieves each course's url and stores them in a list.
    '''

    course_urls = []
    for url in parsed_response.find_all('a'):
        url = url.get('href')
        if 'course' in url.split('/'):
            course_urls.append(url)
    return course_urls


class Course:
    '''
    Treats every course as an object. (This is the best approach).
    '''

    def __init__(self, course_name, section_items):
        self.course_name = course_name
        self.section_items = section_items

    def __repr__(self) -> str:
        return f'<{self.course_name}>'


def is_assignment(item_type):
    '''
    Checks if the item is an assignement.
    '''

    if item_type.lower() == 'assignment':
        return True
    return False


def get_deadline(item_url, headers):
    '''
    Returns the item's deadline only if it's an assignment
    '''

    get_response = BeautifulSoup(get_request(
        item_url, headers).text, 'html.parser')
    return get_response


def multithread(func, items):
    '''
    Runs repeated process with multithreading capability.
    '''

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        return executor.map(func, items)


def fetch_courses(course_urls, headers):
    '''
    Extracts information about each course (name, sections, section items) and wraps them in an object.
    '''

    def get_course_info(url):
        response = get_request(url, headers)
        if response.status_code == 200:
            parsed_response = BeautifulSoup(response.text, 'html.parser')

            # Get course name
            course_name = list(
                map(lambda x: x.strip(), parsed_response.title.text.split('-')))
            course_name = f'[{course_name[0].split()[1]}]{course_name[1]} - {course_name[-1]}'

            # Get course's sections and store them in a list
            course_sections = parsed_response.select(
                '.content > .sectionname > span > a')
            course_sections = list(map(lambda x: x.string, course_sections))

            # Get the items of each section
            section_items = defaultdict(list)
            for i, section_name in enumerate(course_sections):
                items = parsed_response.select(
                    f'#section-{i}>div:nth-child(3)>ul:nth-child(4)>li>div>div>div:nth-child(2)>div>a')

                item_texts = list(map(lambda x: x.text.split(), items))

                item_names = list(map(lambda x: ' '.join(x[:-1]), item_texts))
                item_types = list(map(lambda x: x[-1], item_texts))

                item_urls = list(map(lambda x: x.get('href'), items))

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

    return multithread(get_course_info, course_urls)


def format_section_name(name):
    '''
    This simply formats each section's name that doesn't align to the commont pattern.  
    '''

    try:
        template = 'Pertemuan'
        if name != 'General' and template not in name:
            name = name.split('.')[0]
            return f'{template} {int(name)}'
        return name
    except:
        return name


def format_item_name(name):
    '''
    Splits the item's long ugly name and returns the longest one.
    '''

    try:
        name = list(map(lambda x: x.strip(), name.split('-')))
        return max(name, key=len)
    except:
        return name


def generate_summary(course_objects):
    '''
    Puts everything together in a nicely formatted table.
    '''

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


def logout(headers, parsed_response, start_time):
    '''
    Well, you know what this one does.
    '''

    logout_url = parsed_response.select_one(
        'a.menu-action:nth-child(8)').get('href')
    logout_response = get_request(logout_url, headers)

    if logout_url != logout_response.url:
        print('\n[*] Logout successful!')


def error_message(messages=[]):
    '''
    Prints coustomized error messages.
    '''

    if len(messages) > 1:
        print()
        for message in messages:
            print(f'\t[!] {message}')
    else:
        print(f'\n\n\t[!] {messages[0]}')
    print('\n[!] Program exited.\n')
    exit()


def main():
    '''
    Well, one function to rule them all.
    '''

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'close',
    }

    login_url = ''
    username = ''
    password = ''

    try:
        print()
        while not login_url:
            login_url = input('[!] Login Page URL\t= ')

        while not username:
            username = input('[!] Username\t\t= ')

        while not password:
            password = getpass('[!] Password\t\t= ')

        try:
            start = time()
            done = False

            def animate():
                start = time()
                print()
                for c in itertools.cycle(list('|/-\\')):
                    if done:
                        break
                    sys.stdout.write(
                        f'\r[{c}] Elapsed time: {round(time()-start, 2)} sec(s).')
                    sys.stdout.flush()
                    sleep(.1)
                print()
                sys.stdout.write(
                    f'\r[*] Total time: {round(time()-start, 2)} sec(s).')
                print('\n')

            t = threading.Thread(target=animate)
            t.start()

            # Login process
            parsed_response, headers = attempt_login(
                login_url, headers, username, password)
            print()

            # Course urls extraction after the successful login
            course_urls = get_course_urls(parsed_response)

            # Return a list of course objects
            course_objects = fetch_courses(course_urls, headers)

            # Print summary table
            print()
            print(generate_summary(course_objects))
            print()

            # Logout
            logout(headers, parsed_response, start)
            done = True
            exit()

        except (gaierror, NewConnectionError, MaxRetryError, ConnectionError):
            error_message([
                'A connection error occured! It might be your slow bandwidth.',
                'Fix your connection and try again!'])

        except Exception:
            error_message(['An error occured!'])

    except KeyboardInterrupt:
        error_message(['Oops! Program was interrupted!'])


if __name__ == "__main__":
    main()
