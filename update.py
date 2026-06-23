import datetime
import requests
import os
import hashlib
import time
from lxml import etree

# Ensure cache directory exists
# This script updates the SVG status bars with live GitHub stats.
# Set environment variables ACCESS_TOKEN (GitHub PAT) and USER_NAME (GitHub username) before running.
# Requires lxml library: pip install lxml
os.makedirs('cache', exist_ok=True)
# ── GitHub API auth ──────────────────────────────────────────────────────────
# Fine-grained PAT with: read:Followers, read:Starring, read:Watching
# Repo perms: Commit statuses, Contents, Issues, Metadata, Pull Requests
HEADERS = {'authorization': 'token ' + os.environ['ACCESS_TOKEN']}
USER_NAME = os.environ['USER_NAME']  # your GitHub username
QUERY_COUNT = {
    'user_getter': 0,
    'follower_getter': 0,
    'graph_repos_stars': 0,
    'recursive_loc': 0,
    'graph_commits': 0,
    'loc_query': 0,
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def simple_request(func_name, query, variables):
    """POST to GitHub GraphQL; raise on non-200."""
    request = requests.post(
        'https://api.github.com/graphql',
        json={'query': query, 'variables': variables},
        headers=HEADERS,
    )
    if request.status_code == 200:
        return request
    raise Exception(func_name, 'failed with', request.status_code, request.text, QUERY_COUNT)


def query_count(funct_id):
    global QUERY_COUNT
    QUERY_COUNT[funct_id] += 1


def perf_counter(funct, *args):
    start = time.perf_counter()
    result = funct(*args)
    return result, time.perf_counter() - start


def formatter(label, diff):
    print('{:<23}'.format('   ' + label + ':'), end='')
    if diff > 1:
        print('{:>12}'.format('%.4f' % diff + ' s '))
    else:
        print('{:>12}'.format('%.4f' % (diff * 1000) + ' ms'))


# ── GitHub data fetchers ──────────────────────────────────────────────────────

def user_getter(username):
    """Returns the account ID dict and creation timestamp."""
    query_count('user_getter')
    query = '''
    query($login: String!) {
        user(login: $login) { id createdAt }
    }'''
    req = simple_request(user_getter.__name__, query, {'login': username})
    data = req.json()['data']['user']
    return {'id': data['id']}, data['createdAt']


def follower_getter(username):
    """Returns follower count."""
    query_count('follower_getter')
    query = '''
    query($login: String!) {
        user(login: $login) { followers { totalCount } }
    }'''
    req = simple_request(follower_getter.__name__, query, {'login': username})
    return int(req.json()['data']['user']['followers']['totalCount'])


def graph_repos_stars(count_type, owner_affiliation, cursor=None):
    """Returns total repo count or star count depending on count_type."""
    query_count('graph_repos_stars')
    query = '''
    query($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
                totalCount
                edges {
                    node {
                        ... on Repository {
                            nameWithOwner
                            stargazers { totalCount }
                        }
                    }
                }
                pageInfo { endCursor hasNextPage }
            }
        }
    }'''
    variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME, 'cursor': cursor}
    req = simple_request(graph_repos_stars.__name__, query, variables)
    repos = req.json()['data']['user']['repositories']
    if count_type == 'repos':
        return repos['totalCount']
    elif count_type == 'stars':
        total = sum(e['node']['stargazers']['totalCount'] for e in repos['edges'])
        if repos['pageInfo']['hasNextPage']:
            total += graph_repos_stars('stars', owner_affiliation, repos['pageInfo']['endCursor'])
        return total


def graph_commits(start_date, end_date):
    """Returns total contribution count in a date range."""
    query_count('graph_commits')
    query = '''
    query($start_date: DateTime!, $end_date: DateTime!, $login: String!) {
        user(login: $login) {
            contributionsCollection(from: $start_date, to: $end_date) {
                contributionCalendar { totalContributions }
            }
        }
    }'''
    variables = {'start_date': start_date, 'end_date': end_date, 'login': USER_NAME}
    req = simple_request(graph_commits.__name__, query, variables)
    return int(req.json()['data']['user']['contributionsCollection']['contributionCalendar']['totalContributions'])


# ── Lines-of-code cache system (mirrors Andrew's approach) ───────────────────

def loc_query(owner_affiliation, comment_size=0, force_cache=False, cursor=None, edges=None, max_repos=0):
    """
    Fetches all repos (60 at a time) and delegates to cache_builder.
    Returns [loc_add, loc_del, loc_net, was_cached].
    """
    if edges is None:
        edges = []
    query_count('loc_query')
    query = '''
    query($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 60, after: $cursor, ownerAffiliations: $owner_affiliation) {
                edges {
                    node {
                        ... on Repository {
                            nameWithOwner
                            defaultBranchRef {
                                target {
                                    ... on Commit { history { totalCount } }
                                }
                            }
                        }
                    }
                }
                pageInfo { endCursor hasNextPage }
            }
        }
    }'''
    variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME, 'cursor': cursor}
    req = simple_request(loc_query.__name__, query, variables)
    page = req.json()['data']['user']['repositories']
    if page['pageInfo']['hasNextPage']:
        edges += page['edges']
        return loc_query(owner_affiliation, comment_size, force_cache, page['pageInfo']['endCursor'], edges)
    return cache_builder(edges + page['edges'], comment_size, force_cache)


def cache_builder(edges, comment_size, force_cache, loc_add=0, loc_del=0):
    cached = True
    filename = 'cache/' + hashlib.sha256(USER_NAME.encode()).hexdigest() + '.txt'
    try:
        with open(filename, 'r') as f:
            data = f.readlines()
    except FileNotFoundError:
        data = []
        if comment_size > 0:
            data = ['This line is a comment block.\n'] * comment_size
        with open(filename, 'w') as f:
            f.writelines(data)

    if len(data) - comment_size != len(edges) or force_cache:
        cached = False
        flush_cache(edges, filename, comment_size)
        with open(filename, 'r') as f:
            data = f.readlines()

    cache_comment = data[:comment_size]
    data = data[comment_size:]

    for i, edge in enumerate(edges):
        repo_hash, commit_count, *_ = data[i].split()
        expected_hash = hashlib.sha256(edge['node']['nameWithOwner'].encode()).hexdigest()
        if repo_hash == expected_hash:
            try:
                branch = edge['node']['defaultBranchRef']
                actual_commits = branch['target']['history']['totalCount']
                if int(commit_count) != actual_commits:
                    owner, repo_name = edge['node']['nameWithOwner'].split('/')
                    loc = recursive_loc(owner, repo_name, data, cache_comment)
                    data[i] = (
                        repo_hash + ' ' + str(actual_commits) + ' '
                        + str(loc[2]) + ' ' + str(loc[0]) + ' ' + str(loc[1]) + '\n'
                    )
            except TypeError:
                data[i] = repo_hash + ' 0 0 0 0\n'

    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)

    for line in data:
        parts = line.split()
        loc_add += int(parts[3])
        loc_del += int(parts[4])

    return [loc_add, loc_del, loc_add - loc_del, cached]


def flush_cache(edges, filename, comment_size):
    with open(filename, 'r') as f:
        data = f.readlines()[:comment_size] if comment_size > 0 else []
    with open(filename, 'w') as f:
        f.writelines(data)
        for node in edges:
            f.write(hashlib.sha256(node['node']['nameWithOwner'].encode()).hexdigest() + ' 0 0 0 0\n')


def recursive_loc(owner, repo_name, data, cache_comment, addition_total=0, deletion_total=0, my_commits=0, cursor=None):
    query_count('recursive_loc')
    query = '''
    query($repo_name: String!, $owner: String!, $cursor: String) {
        repository(name: $repo_name, owner: $owner) {
            defaultBranchRef {
                target {
                    ... on Commit {
                        history(first: 100, after: $cursor) {
                            totalCount
                            edges {
                                node {
                                    ... on Commit { committedDate }
                                    author { user { id } }
                                    deletions
                                    additions
                                }
                            }
                            pageInfo { endCursor hasNextPage }
                        }
                    }
                }
            }
        }
    }'''
    variables = {'repo_name': repo_name, 'owner': owner, 'cursor': cursor}
    req = requests.post(
        'https://api.github.com/graphql',
        json={'query': query, 'variables': variables},
        headers=HEADERS,
    )
    if req.status_code == 200:
        branch = req.json()['data']['repository']['defaultBranchRef']
        if branch is not None:
            return loc_counter_one_repo(
                owner, repo_name, data, cache_comment,
                branch['target']['history'], addition_total, deletion_total, my_commits,
            )
        return 0
    force_close_file(data, cache_comment)
    if req.status_code == 403:
        raise Exception('Rate limit hit — anti-abuse limit triggered')
    raise Exception('recursive_loc failed', req.status_code, req.text, QUERY_COUNT)


def loc_counter_one_repo(owner, repo_name, data, cache_comment, history, addition_total, deletion_total, my_commits):
    for node in history['edges']:
        if node['node']['author']['user'] == OWNER_ID:
            my_commits += 1
            addition_total += node['node']['additions']
            deletion_total += node['node']['deletions']
    if not history['edges'] or not history['pageInfo']['hasNextPage']:
        return addition_total, deletion_total, my_commits
    return recursive_loc(
        owner, repo_name, data, cache_comment,
        addition_total, deletion_total, my_commits,
        history['pageInfo']['endCursor'],
    )


def commit_counter(comment_size):
    """Sums commit counts from the cache file."""
    total = 0
    filename = 'cache/' + hashlib.sha256(USER_NAME.encode()).hexdigest() + '.txt'
    with open(filename, 'r') as f:
        data = f.readlines()[comment_size:]
    for line in data:
        total += int(line.split()[2])
    return total


def force_close_file(data, cache_comment):
    filename = 'cache/' + hashlib.sha256(USER_NAME.encode()).hexdigest() + '.txt'
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    print('Partial data saved to', filename, 'before crash.')


# ── SVG updater ───────────────────────────────────────────────────────────────

def svg_overwrite(filename, commit_data, star_data, repo_data, contrib_data, follower_data, loc_data):
    """Parse SVG and inject live GitHub stats into the matching element IDs."""
    tree = etree.parse(filename)
    root = tree.getroot()

    justify_format(root, 'commit_data',   commit_data,   22)
    justify_format(root, 'star_data',     star_data,     14)
    justify_format(root, 'repo_data',     repo_data,      6)
    justify_format(root, 'contrib_data',  contrib_data)
    justify_format(root, 'follower_data', follower_data,  10)
    justify_format(root, 'loc_data',      loc_data[2],    9)
    justify_format(root, 'loc_add',       loc_data[0])
    justify_format(root, 'loc_del',       loc_data[1],    7)

    tree.write(filename, encoding='utf-8', xml_declaration=True)


def justify_format(root, element_id, new_text, length=0):
    """Update element text and adjust dot-leader in the preceding element."""
    if isinstance(new_text, int):
        new_text = '{:,}'.format(new_text)
    new_text = str(new_text)
    find_and_replace(root, element_id, new_text)
    just_len = max(0, length - len(new_text))
    if just_len == 0:
        dot_string = ''
    elif just_len == 1:
        dot_string = ' '
    elif just_len == 2:
        dot_string = '. '
    else:
        dot_string = ' ' + ('.' * just_len) + ' '
    find_and_replace(root, element_id + '_dots', dot_string)


def find_and_replace(root, element_id, new_text):
    element = root.find(f".//*[@id='{element_id}']")
    if element is not None:
        element.text = new_text


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('Calculation times:')

    user_data, user_time = perf_counter(user_getter, USER_NAME)
    OWNER_ID, acc_date = user_data
    formatter('account data', user_time)

    total_loc, loc_time = perf_counter(loc_query, ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'], 7)
    formatter('LOC (cached)' if total_loc[-1] else 'LOC (no cache)', loc_time)

    commit_data, commit_time = perf_counter(commit_counter, 7)
    star_data,   star_time   = perf_counter(graph_repos_stars, 'stars', ['OWNER'])
    repo_data,   repo_time   = perf_counter(graph_repos_stars, 'repos', ['OWNER'])
    contrib_data, contrib_time = perf_counter(graph_repos_stars, 'repos', ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'])
    follower_data, follower_time = perf_counter(follower_getter, USER_NAME)

    for i in range(len(total_loc) - 1):
        total_loc[i] = '{:,}'.format(total_loc[i])

    svg_overwrite('dark.svg',  commit_data, star_data, repo_data, contrib_data, follower_data, total_loc[:-1])
    svg_overwrite('light.svg', commit_data, star_data, repo_data, contrib_data, follower_data, total_loc[:-1])

    print('\n\033[F\033[F\033[F\033[F\033[F\033[F\033[F\033[F',
          '{:<21}'.format('Total function time:'),
          '{:>11}'.format('%.4f' % (user_time + loc_time + commit_time + star_time + repo_time + contrib_time + follower_time)),
          ' s \033[E\033[E\033[E\033[E\033[E\033[E\033[E\033[E', sep='')

    print('Total GitHub GraphQL API calls:', '{:>3}'.format(sum(QUERY_COUNT.values())))
    for fn, count in QUERY_COUNT.items():
        print('{:<28}'.format('   ' + fn + ':'), '{:>6}'.format(count))