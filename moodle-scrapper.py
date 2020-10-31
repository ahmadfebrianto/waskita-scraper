import requests
import urllib3
from bs4 import BeautifulSoup
from getpass import getpass
from time import sleep
from collections import defaultdict
from tabulate import tabulate

from socket import gaierror
from urllib3.exceptions import NewConnectionError, MaxRetryError
from requests.exceptions import ConnectionError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

headers = {
	'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'close',
    }

def get_request(url, headers, login_page=False):
	'''
	Perform GET HTTP request to the login page.
	'''
	response = requests.get(
		url, 
		headers=headers,
		allow_redirects = True
	)

	if login_page:
		# Obtain logintoken from the initial GET request to login page
		login_token = BeautifulSoup(response.text, 'html.parser').select_one('#login > input:nth-child(3)').get('value')
		return response, login_token

	return response


def post_request(url, headers, login_token, username, password):
	'''
	Perform POST HTTP request to submit the login form with the given credentials.
	'''

	response 	= requests.post(url,
		headers = headers,
		data 	= {
			'anchor': '',
			'logintoken':login_token,
			'username':username,
			'password':password
		},
		allow_redirects = True
	)

	return response


def attempt_login(login_url, headers, username, password):
	'''
	Perform the login process starting from GET to POST request sequentially.
	'''

	# Obtain logintoken and MoodleSession
	response, logintoken = get_request(login_url, headers, login_page=True)

	# Append MoodleSession obtained to the headers
	headers['Cookie'] = "MoodleSession=" + response.cookies.get('MoodleSession')

	# Attempt login with logintoken and new headers
	post_request_response = post_request(login_url, headers, logintoken, username, password)
	parsed_response = BeautifulSoup(post_request_response.text, 'html.parser')
	
	if parsed_response.title.text == 'Dashboard':
		print(f'\n[*] Login successful!')

		# Obtain new MoodleSession after successful login
		new_moodle_session = post_request_response.request.headers.get('Cookie').split('=')[1]

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
	course_urls = []
	for url in parsed_response.find_all('a'):
		url = url.get('href')
		if 'course' in url.split('/'):
			course_urls.append(url)
	return course_urls


class CourseObjects:
	
	def __init__(self, course_name, section_items, response):
		self.course_name = course_name
		self.section_items = section_items
		self.response = response

	def __repr__(self) -> str:
		return f'<{self.course_name}>'


def extract_courses(course_urls, headers):
	course_objects = []
	for url in course_urls:
		sleep(0.5)
		response = get_request(url, headers)
		if response.status_code == 200:
			parsed_response =  BeautifulSoup(response.text, 'html.parser')

			# Get course name
			course_name = list(map(lambda x: x.strip(), parsed_response.title.text.split('-'))) 
			course_name = f'[{course_name[0].split()[1]}]{course_name[1]} - {course_name[-1]}' 
			
			# Get course section list
			course_sections = parsed_response.select('.content > .sectionname > span > a')
			course_sections = list(map(lambda x: x.string, course_sections))

			# Get course sections and items
			section_items = defaultdict(dict)
			for i, section_name in enumerate(course_sections):
				items = parsed_response.select(f'#section-{i}>div:nth-child(3)>ul:nth-child(4)>li>div>div>div:nth-child(2)>div>a')
				item_names = list(map(lambda x: ' '.join(x.text.split()[:-1]), items))
				item_urls = list(map(lambda x: x.get('href'), items))

				for item, url in zip(item_names, item_urls):
					section_items[section_name][item] = url
				
			course_objects.append(CourseObjects(course_name, section_items, parsed_response))
			
		else:
			continue
		
	return course_objects


def format_section_name(name):
	try:
		template = 'Pertemuan'
		if name != 'General' and template not in name:
			name = name.split('.')[0]
			return f'{template} {int(name)}'
		return name
	except:
		return name


def format_item_name(name):
	try:
		name = list(map(lambda x: x.strip(), name.split('-')))
		return max(name, key=len)
	except:
		return name


def summary(course_objects):
	tables = []
	headers = ['ID', 'Course Name', 'Recent Section', 'Section Items']
	table_format = 'fancy_grid'

	for course in course_objects:
		# Course ID
		id = course.course_name[:7][1:-1]

		# Course name
		name = course.course_name[7:]

		# Section name
		recent_section = format_section_name(list(course.section_items.items())[-1][0])

		section_items = ''
		items = list(course.section_items.items())[-1][1].items()
		for item_name, url in items:
			section_items += format_item_name(item_name) + '\n' + url + '\n\n'

		tables.append([id, name, recent_section, section_items])

	return tabulate(tables, headers=headers, tablefmt=table_format, colalign=('left','left','left'))


def logout(headers, parsed_response):
	logout_url 		= parsed_response.select_one('a.menu-action:nth-child(8)').get('href')
	logout_response = get_request(logout_url, headers)

	if logout_url != logout_response.url:
		print('\n[*] Logout successful!')
		print('\n[!] Program exited.\n')
		exit()


def error_message(messages=[]):
	if len(messages) > 1:
		print()
		for message in messages:
			print(f'\t[!] {message}')
	else:
		print(f'\n\n\t[!] {messages[0]}')
	print('\n[!] Program exited.\n')
	exit()


def main():
	headers = {
	'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'close',
    }

	login_url 	= ''
	username 	= ''
	password 	= ''

	try:
		print()
		while not login_url:
			login_url = input('[!] Login Page URL\t= ')

		while not username:
			username = input('[!] Username\t\t= ')
				
		while not password:
			password = getpass('[!] Password\t\t= ')

		try:
			# Login process
			parsed_response, headers = attempt_login(login_url, headers, username, password)
			print()

			# Course extraction after successful login
			course_urls = get_course_urls(parsed_response)
			course_objects = extract_courses(course_urls, headers=headers)

			# Print summary table
			print(summary(course_objects))
			print()
			
			# Logout
			logout(headers, parsed_response)
		
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
