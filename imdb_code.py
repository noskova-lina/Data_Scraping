from imdb_helper_functions import *


def get_actors_by_movie_soup(cast_page_soup, num_of_actors_limit=None) -> dict:
    actors_dict = {}

    table = cast_page_soup.find('table', attrs={"class": "cast_list"})
    rows = table.find_all('tr')

    counter = 0
    for row in rows:
        if row.get("class") is None:
            continue

        if num_of_actors_limit is not None and counter >= num_of_actors_limit:
            break

        a = row.find_all("a")[1]
        actors_dict[URL + a['href'].split("?ref_")[0]] = a.text.strip()
        counter += 1

    return actors_dict


def get_movies_by_actor_soup(cast_page_soup: BeautifulSoup, num_of_movies_limit=None) -> dict:
    movies_dict = {}

    block = cast_page_soup.find_all("div", attrs={"class": "ipc-accordion--base"})[1]
    movies = block.find_all("div", attrs={"class": "ipc-metadata-list-summary-item__tc"})

    counter = 0
    for movie in movies:
        ul = movie.find_all('ul')
        if len(ul) > 1:
            continue

        if num_of_movies_limit is not None and counter >= num_of_movies_limit:
            break

        a = movie.find("a")
        movies_dict[URL + a['href'].split("?ref_")[0] + "fullcredits"] = a.text
        counter += 1

    return movies_dict


def get_movie_distance(cache: SyncMap, actor_start_url, actor_end_url, num_of_actors_limit=None, num_of_movies_limit=None):
    seen_actors = {}
    actors = {actor_start_url: None}
    distance = 1
    while True:
        if distance > 3:
            cache.dump("dump.json")
            return actor_start_url, actor_end_url, np.inf
        actors = process_actors(cache, actors, actor_end_url, seen_actors, num_of_actors_limit, num_of_movies_limit)
        if actors is None:
            cache.dump("dump.json")
            return actor_start_url, actor_end_url, distance
        distance += 1


def get_movie_descriptions_by_actor_soup(actor_page_soup: BeautifulSoup) -> list:
    descriptions = []

    movies = get_movies_by_actor_soup(actor_page_soup)
    for url in movies:
        descriptions.append(get_movie_description(url.strip("fullcredits")))

    return descriptions


# I'm so sorry for this. But I don't want to make cyclic imports
def get_movies_by_actor_url(url: str, num_of_movies_limit=None) -> dict:
    soup = get_soup_from_driver(url, 'ipc-see-more__button', 1)
    return get_movies_by_actor_soup(soup, num_of_movies_limit=num_of_movies_limit)


# I'm so sorry for this. But I don't want to make cyclic imports
def get_actors_by_movie_url(url: str, num_of_actors_limit=None) -> dict:
    soup = get_soup(url)
    return get_actors_by_movie_soup(soup, num_of_actors_limit=num_of_actors_limit)


# I'm so sorry for this. But I don't want to make cyclic imports
def process_actor(cache: SyncMap, actor_start_url: str, actor_end_url: str, num_of_actors_limit=None, num_of_movies_limit=None) -> (dict, bool):
    if actor_start_url not in cache:
        cache[actor_start_url] = get_movies_by_actor_url(actor_start_url, num_of_movies_limit)
    movies_for_actor = cache[actor_start_url]

    actors = {}
    for url, movie in movies_for_actor.items():
        if url not in cache:
            cache[url] = get_actors_by_movie_url(url, num_of_actors_limit)
        actors.update(cache[url])

        if actor_end_url in actors:
            return {}, True

    return actors, False


# I'm so sorry for this. But I don't want to make cyclic imports
def process_actors(cache: SyncMap, actors, actor_end_url, seen_actors, num_of_actors_limit, num_of_movies_limit):
    actors_for_process = {}
    for actor in actors:
        if actor in seen_actors:
            continue
        seen_actors[actor] = None
        try:
            actors_batch, find = process_actor(cache, actor, actor_end_url, num_of_actors_limit, num_of_movies_limit)
        except Exception:
            continue
        if find:
            return None
        actors_for_process.update(actors_batch)

    return actors_for_process
