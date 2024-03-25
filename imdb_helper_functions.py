from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import numpy as np
import concurrent.futures
from tqdm import tqdm
import itertools
import time
import requests
import threading
import typing
import json

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
URL = "https://www.imdb.com"
NUMBER_OF_THREADS = 8


def get_soup(url: str) -> BeautifulSoup:
    response = requests.get(url, headers={'User-Agent': USER_AGENT})
    if response.status_code != 200:
        return None
    return BeautifulSoup(response.text, 'lxml')


def get_driver(url: str, startup_window: bool) -> webdriver:
    chrome_options = Options()
    chrome_options.add_argument("user-agent="+USER_AGENT)
    if not startup_window:
        chrome_options.add_argument('--headless')
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    return driver


def wait_until_element_is_loaded(driver, element_class: str, timeout: int):
    wait = WebDriverWait(driver, timeout)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, element_class)))


def wait_until_button_is_clickable(driver, button_class: str, timeout: int):
    wait = WebDriverWait(driver, timeout)
    return wait.until(EC.element_to_be_clickable((By.CLASS_NAME, button_class)))


def click_button(driver, button_class: str, timeout: int):
    wait_until_element_is_loaded(driver, button_class, timeout)
    button = wait_until_button_is_clickable(driver, button_class, timeout)
    driver.execute_script("arguments[0].click();", button)


def make_clicks(driver, button_class: str, timeout: int):
    while True:
        try:
            click_button(driver, button_class, timeout)
        except Exception:
            return
        time.sleep(timeout)


def get_soup_from_driver(url: str, button_class: str, timeout: int) -> BeautifulSoup:
    driver = get_driver(url, False)
    make_clicks(driver, button_class, timeout)
    page_source = driver.page_source
    driver.close()
    return BeautifulSoup(page_source, 'lxml')


def print_movies(movies):
    for movie in movies:
        print(f"Movie: {movie[0]}\nLink: {movie[1]}")


def print_actors(actors):
    for actor in actors:
        print(f"Actor: {actor[0]}\nLink: {actor[1]}")


# basic RW mutex
class ReadWriteLock:
    def __init__(self):
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0

    def acquire_read(self):
        self._read_ready.acquire()
        try:
            self._readers += 1
        finally:
            self._read_ready.release()

    def release_read(self):
        self._read_ready.acquire()
        try:
            self._readers -= 1
            if not self._readers:
                self._read_ready.notify_all()
        finally:
            self._read_ready.release()

    def acquire_write(self):
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()

    def release_write(self):
        self._read_ready.release()


class SyncMap:
    def __init__(self):
        self.map = {}
        self.RWLock = ReadWriteLock()

    def __setitem__(self, key: typing.Any, value: typing.Any):
        self.RWLock.acquire_write()
        self.map[key] = value
        self.RWLock.release_write()

    def __getitem__(self, key: typing.Any) -> typing.Any:
        self.RWLock.acquire_read()
        b = self.map[key]
        self.RWLock.release_read()
        return b

    def __contains__(self, key: typing.Any) -> bool:
        self.RWLock.acquire_read()
        b = key in self.map
        self.RWLock.release_read()
        return b

    def __repr__(self):
        return self.map.__repr__()

    def update(self, data: dict):
        self.RWLock.acquire_write()
        self.map.update(data)
        self.RWLock.release_write()

    def dump(self, path: str):
        self.RWLock.acquire_read()
        with open(path, 'w') as f:
            json.dump(self.map, f)
        self.RWLock.release_read()

    def restore(self, path: str):
        with open(path, 'r') as f:
            self.map = json.load(f)


def edge_color_mapping(movie_distance, edge_colors):
    return edge_colors.get(movie_distance, 'black')


def find(data: list, key: str) -> str:
    for i in data:
        if i[0] == key:
            return i[1]
    return ''


def get_movie_description(url: str):
    soup = get_soup(url)
    el = soup.find("span", attrs={"data-testid": "plot-l", "role": "presentation"})
    if el is None:
        return None
    return el.text
