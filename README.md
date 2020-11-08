# moodle-scraper
A Moodle-based LMS scraper written in Python 3.

### Descriptions

This is a web scraper written in Python 3 made specifically for scraping Moodle-based Learning Management System website. I created this program to collect the information about the courses I enrolled in on the Moodle-based LMS owned by my local community. All the information collected is then processed and presented in a nicely formatted table. It might be a trivial thing, if you would say, but this does save me a whole lot of time rather than having do that manually on a browser.

This scraper is capable of performing the following tasks:
* getting the recent section of each course I enrolled in.
* getting the section's items as well as the deadline if there's an assignment.

[![Demo](https://img.youtube.com/vi/oHU6YzUlsOQ/0.jpg)](https://www.youtube.com/watch?v=oHU6YzUlsOQ)

#### Important Notes:
*Since Moodle is implemented in many different ways by each party/organisation around the world, it's expected to have different web structures in their respective. Therefore, chances are you would encounter errors or this script might not work as expected. In that case, however, **you must modify this script in order to make it work on your target website** (again, make sure it's a Moodle-based LMS). If you opt to modify this script, I advise you start rewriting your own version after the first three functions as they're the most critical parts in this script.*

#### Built With:
* Python 3

#### Tested On:
* Windows 10
* Linux Mint 20.x
* Kali Linux 2020.x

### Prerequisites:
  ```python
  pip3 install -r requirements.txt
  ```

### Usage
* **RECOMMENDED** - You must **edit the main file** *(moodle-scraper.py)* and provide the login page URL and your credentials in the **main()** section.
```python
def main():
  ......
  login_url = 'https://example.com/login'
  username  = 'your_username'
  password  = 'your_password'
```

* **NOT RECOMMENDED** - You can just run the main file (moodle-lms-scraper.py) directly, but you'll have to manually input the login page URL and your credentials each time you want to login. This is a tedious one, though. Hence, not a recommendation.
```python
python3 moodle-scraper.py
```

### Contact(s)
* <a href="mailto:achmadfebryanto@gmail.com">Email</a>
