#!/usr/bin/env python3

import requests
import xml.etree.ElementTree as ET
import subprocess
import html2text
import os
import re
#import sys
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup  # New import


#need this to get it to run under cron
PYTHONPATH="/usr/local/Cellar/python@3.11/3.11.6/Frameworks/Python.framework/Versions/3.11/lib"
    
# Constants
FEED_URL = "http://www.yoursite.org/?feed=atom"
JOURNAL_NAME = "Wordpress Entries"
TAGS = ["imported by dowppy"]
DOWPPY_DIR = os.path.join(os.path.expanduser('~'), '.dowppy')
CONFIG_FILE = os.path.join(DOWPPY_DIR, 'config.txt')
IMAGE_DIR = os.path.join(DOWPPY_DIR, 'images')

def ensure_image_directory():
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)

def fetch_atom_feed(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.content

def parse_atom_feed(feed_content):
    root = ET.fromstring(feed_content)
    entries = []
    for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
        title = entry.find('{http://www.w3.org/2005/Atom}title').text
        published = entry.find('{http://www.w3.org/2005/Atom}published').text
        content = entry.find('{http://www.w3.org/2005/Atom}content').text
        image_url = extract_image_url(content)
        entries.append((title, published, content, image_url))
    return entries

def extract_image_url(content):
    matches = re.findall(r'src="([^"]+\.jpe?g)"', content)
    return matches[0] if matches else None

def download_image(image_url, published_date):
    if image_url:
        image_name = published_date.split("T")[0] + ".jpg"
        image_path = os.path.join(IMAGE_DIR, image_name)
        response = requests.get(image_url)
        with open(image_path, 'wb') as file:
            file.write(response.content)
        return image_path
    return None

def convert_html_to_markdown(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove all image tags from the content
    for img_tag in soup.find_all('img'):
        img_tag.decompose()

    # Convert the updated HTML content to Markdown
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.body_width = 0  # This will prevent line wrapping within links
    return h.handle(str(soup))


def format_entry_content(title, content):
    markdown_title = f"## {title}\n\n"
    return markdown_title + content

def create_day_one_entry(date, content, journal_name, tags, attachments=[]):
    cmd = ['dayone2', 'new', '--date', date, '--journal', journal_name]
    cmd += ['--tags'] + tags
    if attachments:
        cmd.extend(['-a'] + attachments)
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
    process.communicate(input=content)

def is_entry_after_start_date(entry_date, start_date):
    entry_date_obj = datetime.strptime(entry_date.split("T")[0], "%Y-%m-%d")
    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
    return entry_date_obj >= start_date_obj
    
def read_last_execution_datetime():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as file:
            return datetime.fromisoformat(file.read().strip())
    return None

def update_last_execution_datetime(date_time_obj):
    with open(CONFIG_FILE, 'w') as file:
        file.write(date_time_obj.isoformat())

def is_entry_newer_than_last_execution(entry_datetime, last_execution_datetime):
    return not last_execution_datetime or entry_datetime > last_execution_datetime
    
def delete_image_files():
    for file_name in os.listdir(IMAGE_DIR):
        file_path = os.path.join(IMAGE_DIR, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)
    print("All image files have been deleted.")

def main():
    if not os.path.exists(DOWPPY_DIR):
        os.makedirs(DOWPPY_DIR)
    ensure_image_directory()

    last_execution_datetime = read_last_execution_datetime()
    try:
        feed_content = fetch_atom_feed(FEED_URL)
        entries = parse_atom_feed(feed_content)
        latest_datetime = last_execution_datetime
        for title, published, content, image_url in entries:
            entry_datetime = datetime.fromisoformat(published)
            if is_entry_newer_than_last_execution(entry_datetime, last_execution_datetime):
                if not latest_datetime or entry_datetime > latest_datetime:
                    latest_datetime = entry_datetime
                markdown_content = convert_html_to_markdown(content)
                formatted_content = format_entry_content(title, markdown_content)
                image_path = download_image(image_url, published)
                create_day_one_entry(published, formatted_content, JOURNAL_NAME, TAGS, [image_path] if image_path else [])
                print(f"Entry added for date and time: {published} with title: {title}")

        if latest_datetime:
            update_last_execution_datetime(latest_datetime)
        # Call the function to delete images after processing is complete
            delete_image_files()
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
