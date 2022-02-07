from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from time import sleep
from os import path
from math import ceil
import grequests
import json

REQUEST_TPL = ('https://api.nytimes.com/svc/search/v2/articlesearch.json?'
               'fq=headline:("deaf" "hard-of-hearing" "hard of hearing" '
               '"sign language" "cochlear impant" "hearing impaired" '
               '-"tone deaf" -"deaf ears") AND day_of_week:'
               '({first_half}"Sunday" {first_half}"Saturday" {first_half}"Friday")'
               '&page={page}&api-key={key}')
ARTICLES_PER_PAGE = 10

# The function used to scrape article HTML for the text
def scrape_article(html):
    soup = BeautifulSoup(html, 'html5lib')

    # Scrape for the main site
    content = soup.find('section', {'class': 'meteredContent'})

    # If it doesn't work, try the scrape for their blog sites
    if not content:
        content = soup.find('div', {'class': 'entry-content'})

    if content:
        return content.text
    else:
        return ''

# Retrieving our API key
with open('./nyt_api.key') as f:
    key = f.read().strip()

# We needed to split the dataset in half to be able to access all of it
# This is because the API limits you to accessing the first 200 pages
# The easiest way to arbitrarily split the data is by which day an article
#   was published on
first_half = '' if input('First half of the data (y/n): ') == 'y' else '-'

# In case we halt our queries early, we can resume part way through
start_page = int(input('Starting page: '))

# Retrieving what data we have so far
data = []
if path.exists('./nyt_data.json'):
    with open('./nyt_data.json', 'r') as f:
        data = json.load(f)
    

# We can only access up to page 200 (2000 articles)
page = start_page
max_pages = 200
while page < max_pages:
    # We are only allowed 10 requests a minute, so one every 6 seconds
    # 6.1 to be safe
    next_request_time = datetime.now() + timedelta(seconds=6.1)

    # Getting the api_page
    urls = [REQUEST_TPL.format(first_half=first_half, page=page, key=key)]
    requests = (grequests.get(u) for u in urls)
    responses = grequests.map(requests)
    api_page = responses[0].json()

    # Updating the max number of pages we have access to
    if api_page and 'response' in api_page and 'meta' in api_page['response'] and 'hits' in api_page['response']['meta']:
        max_pages = min(200, ceil(api_page['response']['meta']['hits'] / ARTICLES_PER_PAGE))
    
    # Parsing the api_page
    articles = []
    if api_page and 'response' in api_page and 'docs' in api_page['response']:
        for article in api_page['response']['docs']:                
            if 'word_count' in article and article['word_count'] < 1:
                # This occurs for some old archived articles
                # We can't scrape them, so discard them
                continue

            # Parsing each article into its metadata
            metadata = {}
            
            if 'web_url' in article:
                metadata['url'] = article['web_url']
            else:
                # If there somehow isn't a url, we should skip it
                print(f'Missing url on page {page}')
                continue

            if 'headline' in article and 'main' in article['headline']:
                metadata['headline'] = article['headline']['main']
            
            if 'pub_date' in article:
                metadata['date'] = article['pub_date']
            
            if 'source' in article:
                metadata['source'] = article['source']
            
            articles.append(metadata)

    else:
        print(f'Failed at page {page}')
        break
        
    # Now we can concurrently scrape all the articles
    # This is where grequests comes in useful
    # This is much faster than individually scraping them
    urls = [m['url'] for m in articles]
    requests = (grequests.get(u) for u in urls)
    responses = grequests.map(requests)

    # Now we can scrape the HTML for the relevant text
    for r, m in zip(responses, articles):
        if r:
            m['text'] = scrape_article(r.content)
            if m['text'] == '':
                print(f'Failed to scrape {m["text"]}')
                m['error'] = 'Failed to scrape'
        else:
            print(f'Request failed for {m["url"]}')
            m['error'] = str(r)

    # Writing the data to our file
    data += articles
    with open('./nyt_data.json', 'w') as f:
        json.dump(data, f)
    
    # We can also write the page to a file, just in case of crashes
    #   it'll allow for an easy continuation later
    with open('./nyt_data_page.txt', 'w') as f:
        f.write(f'Page: {page}\n')

    print(f'Processed page {page} / {max_pages}')
    page += 1

    # Now waiting until next_request_time
    wait_time = next_request_time - datetime.now()

    # If there is a positive amount of time remaining
    # Things can get screwy with negative time values without this check
    if wait_time > timedelta(seconds=0):
        sleep(wait_time.seconds + wait_time.microseconds / 1000000)
