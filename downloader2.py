import os
import argparse
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from tqdm import tqdm
import time
import logging
import re
import threading
from queue import Queue
import random
from fake_useragent import UserAgent

# Logger configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Dynamic User-Agent for requests
ua = UserAgent()
HEADERS = {
    'User-Agent': ua.random
}

# Extended list of supported file types for web development and common web-related files
ALL_RESOURCE_TYPES = [
    '.php', '.php2', '.php3', '.php4', '.php5', '.html', '.htm', '.xhtml', '.css', '.scss', 
    '.js', '.mjs', '.json', '.asp', '.aspx', '.axd', '.ashx', '.cshtml', '.jsp', '.jspx', 
    '.java', '.c', '.cpp', '.h', '.cs', '.pl', '.py', '.rb', '.rhtml', '.erb', '.xml', '.xsl',
    '.xslt', '.svg', '.json', '.yaml', '.yml', '.md', '.txt', '.xml', '.jspa', '.jstl', '.dhtml',
    '.shtml', '.phtml', '.razor', '.csp', '.jspx', '.md', '.css', '.scss', '.sass', '.less',
    '.pyc', '.dll', '.cgi', '.pl', '.swift', '.kt', '.jar', '.war', '.ear', '.zip', '.tar', '.gz',
    '.rar', '.7z', '.bz2', '.dmg', '.iso', '.shar', '.xz', '.pem', '.p7b', '.p7c', '.p12',
    '.crt', '.cer', '.key', '.der', '.csr', '.eot', '.woff', '.woff2', '.ttf', '.otf', '.psd',
    '.ai', '.svg', '.bmp', '.gif', '.jpeg', '.jpg', '.png', '.webp', '.ico', '.mp3', '.wav',
    '.flac', '.mp4', '.avi', '.mov', '.mkv', '.ogv', '.ogx', '.ogm', '.ogv', '.ogg', '.oga',
    '.webm', '.m4v', '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.odt', 
    '.ods', '.odp', '.otf', '.otg', '.ott', '.wpd', '.wps', '.xps', '.csv', '.rtf', '.zip',
    '.tar.gz', '.tar.bz2', '.tgz', '.xz', '.7z', '.rar', '.tar', '.war', '.ear', '.jar'
]

def print_banner():
    # ANSI escape codes for colors
    RED = '\033[31m'
    WHITE = '\033[37m'
    RESET = '\033[0m'

    # Banner design with colors
    banner = f"""
{RED} ________       __    _______            __    __    __                
|  |  |  .-----|  |--|     __.----.---.-|  |--|  |--|  .-----.----.    
|  |  |  |  -__|  _  |    |  |   _|  _  |  _  |  _  |  |  -__|   _|    
|________|_____|_____|_______|__| |___._|_____|_____|__|_____|__| {RESET}

{WHITE}Pro Version{RESET}
{RED}Created by ibrahimsql{RESET}
    """
    print(banner)

def sanitize_filename(filename):
    """Remove invalid characters from filenames."""
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

def make_dirs(path):
    if not os.path.exists(path):
        os.makedirs(path)

def is_valid_url(url):
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)

def get_page(session, url, retries=3):
    """Fetch the requested URL and return the response. Retries if necessary."""
    for attempt in range(retries):
        try:
            response = session.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            save_cookies(session.cookies, 'cookies.txt')
            return response.text
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching URL: {url} - Error: {e}")
            if attempt + 1 < retries:
                logging.info(f"Retrying {attempt + 1}/{retries}...")
                time.sleep(2)
            else:
                logging.error(f"Failed to fetch URL: {url} - {e}")
                return None

def save_file(session, url, save_path, max_file_size=None, overwrite=False):
    """Download a file and save it to the specified directory."""
    for attempt in range(3):
        try:
            response = session.get(url, headers=HEADERS, stream=True, timeout=10)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))

            if max_file_size and total_size > max_file_size:
                logging.warning(f"File {url} exceeds max size ({max_file_size} bytes), skipping.")
                return False

            save_path = sanitize_filename(save_path)

            if os.path.exists(save_path) and not overwrite:
                logging.info(f"File already exists: {save_path}, skipping.")
                return False

            with open(save_path, 'wb') as file, tqdm(
                desc=save_path,
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for data in response.iter_content(chunk_size=1024):
                    size = file.write(data)
                    bar.update(size)
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to download file: {url} - Error: {e}")
            if attempt + 1 < 3:
                logging.info(f"Retrying {attempt + 1}/3...")
                time.sleep(2)
            else:
                logging.error(f"Failed to download file: {url} - {e}")
                return False

def parse_and_download(session, url, base_url, save_dir, visited, delay, max_depth, current_depth=0, exclude_types=[], max_file_size=None, overwrite=False, queue=None):
    """Parse the specified URL and download resources."""
    if current_depth > max_depth:
        return

    if url in visited:
        return
    visited.add(url)

    html_content = get_page(session, url)
    if html_content is None:
        return

    parsed_url = urlparse(url)
    path = parsed_url.path
    if path.endswith('/'):
        path += 'index.html'
    elif not os.path.splitext(path)[1]:
        path += '/index.html'

    save_path = os.path.join(save_dir, path.lstrip('/'))
    make_dirs(os.path.dirname(save_path))

    soup = BeautifulSoup(html_content, 'html.parser')

    tags = {
        'img': 'src',
        'script': 'src',
        'link': 'href',
        'a': 'href',
        'video': 'src',
        'audio': 'src',
        'source': 'src'
    }

    for tag, attr in tags.items():
        for resource in soup.find_all(tag):
            src = resource.get(attr)
            if not src or 'nofollow' in resource.attrs.get('rel', []):
                continue
            resource_url = urljoin(url, src)
            resource_parsed_url = urlparse(resource_url)
            resource_ext = os.path.splitext(resource_parsed_url.path)[1]

            if resource_ext.lower() in ALL_RESOURCE_TYPES or tag == 'a':
                if any(resource_ext.lower() == ext for ext in exclude_types):
                    logging.info(f"Skipping file {resource_url} due to excluded extension ({resource_ext}).")
                    continue

                resource_path = os.path.join(save_dir, sanitize_filename(resource_parsed_url.path.lstrip('/')))
                make_dirs(os.path.dirname(resource_path))

                if is_valid_url(resource_url) and resource_url not in visited:
                    if resource_ext.lower() in ALL_RESOURCE_TYPES:
                        if queue is None:
                            save_file(session, resource_url, resource_path, max_file_size=max_file_size, overwrite=overwrite)
                        else:
                            queue.put((resource_url, resource_path, max_file_size, overwrite))
                    elif tag == 'a':
                        parse_and_download(session, resource_url, base_url, save_dir, visited, delay, max_depth, current_depth + 1, exclude_types, max_file_size, overwrite, queue)

    save_path = sanitize_filename(save_path)
    with open(save_path, 'w', encoding='utf-8') as file:
        file.write(soup.prettify())
        logging.info(f"Saved: {save_path}")

    time.sleep(delay)

def save_cookies(cookies, filename):
    """Save cookies to a file."""
    with open(filename, 'w') as f:
        for cookie in cookies:
            f.write(f"{cookie.name}={cookie.value}; domain={cookie.domain}; path={cookie.path}\n")

def load_cookies(session, filename):
    """Load cookies from a file and add them to the session."""
    if not os.path.exists(filename):
        return
    with open(filename, 'r') as f:
        for line in f:
            cookie = line.strip().split(';')[0]
            if cookie:
                name, value = cookie.split('=', 1)
                session.cookies.set(name.strip(), value.strip())

def worker(session, queue):
    """Function for threads to process the queue."""
    while not queue.empty():
        try:
            url, save_path, max_file_size, overwrite = queue.get()
            save_file(session, url, save_path, max_file_size=max_file_size, overwrite=overwrite)
            queue.task_done()
        except Exception as e:
            logging.error(f"Thread error: {e}")

def main():
    print_banner()

    parser = argparse.ArgumentParser(description='Advanced Website Downloader')
    parser.add_argument('url', help='Target website URL')
    parser.add_argument('-d', '--dir', default='downloaded_site', help='Directory to save files')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests (seconds)')
    parser.add_argument('--depth', type=int, default=1, help='Maximum crawl depth')
    parser.add_argument('--user-agent', default=HEADERS['User-Agent'], help='Custom User-Agent')
    parser.add_argument('--timeout', type=int, default=10, help='Timeout for each request (seconds)')
    parser.add_argument('--log-file', default=None, help='File path to save logs')
    parser.add_argument('--no-recursion', action='store_true', help='Download only the main page without following links')
    parser.add_argument('--include-media', action='store_true', help='Download media files (images, videos)')
    parser.add_argument('--exclude-types', type=str, help='Specify file extensions to exclude (.png,.jpg)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing files')
    parser.add_argument('--retry', type=int, default=3, help='Number of retries for a request')
    parser.add_argument('--proxy', type=str, help='Proxy server (e.g. http://proxyserver:port)')
    parser.add_argument('--headers', type=str, help='Add custom HTTP headers (e.g. "Authorization: Bearer token")')
    parser.add_argument('--cookies', type=str, help='Add custom cookies (e.g. "sessionid=abcd1234; csrftoken=xyz9876")')
    parser.add_argument('--ignore-certs', action='store_true', help='Ignore SSL certificate errors')
    parser.add_argument('--silent', action='store_true', help='Show only critical errors (silent mode)')
    parser.add_argument('--max-file-size', type=int, help='Specify maximum file size to download in bytes')
    parser.add_argument('--output-format', type=str, help='Specify naming format for saved files')
    parser.add_argument('--auth', type=str, help='Add username and password for HTTP Basic Authentication (e.g. "username:password")')
    parser.add_argument('--threads', type=int, default=4, help='Number of concurrent threads')
    parser.add_argument('--rate-limit', type=int, default=30, help='Maximum requests per minute')
    parser.add_argument('--all', action='store_true', help='Download all web-related file types')
    args = parser.parse_args()

    global HEADERS
    HEADERS['User-Agent'] = args.user_agent

    if args.log_file:
        file_handler = logging.FileHandler(args.log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logging.getLogger().addHandler(file_handler)

    if args.silent:
        logging.getLogger().setLevel(logging.CRITICAL)

    if not is_valid_url(args.url):
        logging.error("Invalid URL. Please enter a correct URL.")
        return

    make_dirs(args.dir)
    visited = set()

    # Use all file types if --all is specified
    resource_types = ALL_RESOURCE_TYPES if args.all else []

    exclude_types = args.exclude_types.split(',') if args.exclude_types else []

    session = requests.Session()

    load_cookies(session, 'cookies.txt')

    if args.cookies:
        cookies = {}
        for cookie in args.cookies.split(';'):
            key, value = cookie.strip().split('=', 1)
            cookies[key] = value
        session.cookies.update(cookies)

    if args.proxy:
        session.proxies = {"http": args.proxy, "https": args.proxy}

    if args.ignore_certs:
        session.verify = False

    if args.headers:
        for header in args.headers.split(';'):
            key, value = header.strip().split(':', 1)
            HEADERS[key.strip()] = value.strip()

    HEADERS['User-Agent'] = random.choice(ua.data_browsers['all'])

    queue = Queue()

    threads = []
    for _ in range(args.threads):
        thread = threading.Thread(target=worker, args=(session, queue))
        thread.start()
        threads.append(thread)

    parse_and_download(session, args.url, args.url, args.dir, visited, args.delay, args.depth if not args.no-recursion else 0, exclude_types, args.max_file_size, args.overwrite, queue)

    queue.join()

    for thread in threads:
        thread.join()

    logging.info("All tasks completed.")

if __name__ == '__main__':
    main()
