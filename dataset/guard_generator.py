from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from time import sleep
from os import path
import grequests
import json

REQUEST_TPL = ('https://content.guardianapis.com/search?q=('
               '"deaf" "hard-of-hearing" "hard of hearing" "sign language" '
               '"cochlear implant" "hearing impaired") AND NOT '
               '("tone deaf" "deaf ears" "deaf ear")&page={page}'
               '&page-size={page_size}&api-key={key}')
ARTICLES_PER_PAGE = 20

# The function used to scrape article HTML for the text
def scrape_article(html):
    soup = BeautifulSoup(html, 'html5lib')

    # Scrape for the main site
    headline = soup.find('h1')
    content = soup.find('div', {'id': 'maincontent'})

    headline = headline.text if headline else ''
    content = content.text if content else ''

    return headline, content

# Retrieving our API key
with open('./guard_api.key') as f:
    key = f.read().strip()

# In case we halt our queries early, we can resume part way through
start_page = int(input('Starting page: '))

# Retrieving what data we have so far
data = []
if path.exists('./guard_data.json'):
    with open('./guard_data.json', 'r') as f:
        data = json.load(f)
    

page = max(start_page, 1)
max_pages = page
while page <= max_pages:
    # We can make a lot more requests than this
    #   (12 requests a second, with 50 results a page)
    # But that would be a ridiculous amount of data to request
    # So this will be slower, but more reasonable
    next_request_time = datetime.now() + timedelta(seconds=3)

    # Getting the api_page
    urls = [REQUEST_TPL.format(page=page, page_size=ARTICLES_PER_PAGE, key=key)]
    requests = (grequests.get(u) for u in urls)
    responses = grequests.map(requests)
    api_page = responses[0].json()

    # Updating the max number of pages we have access to
    if api_page and 'response' in api_page and 'pages' in api_page['response']:
        max_pages = api_page['response']['pages']
    
    # Parsing the api_page
    articles = []
    if api_page and 'response' in api_page and 'results' in api_page['response']:
        for article in api_page['response']['results']:                
            # Parsing each article into its metadata
            metadata = {}
            
            if 'webUrl' in article:
                metadata['url'] = article['webUrl']
            else:
                # If there somehow isn't a url, we should skip it
                print(f'Missing url on page {page}')
                continue
            
            if 'webPublicationDate' in article:
                metadata['date'] = article['webPublicationDate']
            
            metadata['source'] = 'The Guardian'
            
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
            m['headline'], m['text'] = scrape_article(r.content)
            if m['text'] == '' or m['headline'] == '':
                print(f'Failed to scrape {m["text"]}')
                m['error'] = 'Failed to scrape'
        else:
            print(f'Request failed for {m["url"]}')
            m['error'] = str(r)

    # Writing the data to our file
    data += articles
    with open('./guard_data.json', 'w') as f:
        json.dump(data, f)
    
    # We can also write the page to a file, just in case of crashes
    #   it'll allow for an easy continuation later
    with open('./guard_data_page.txt', 'w') as f:
        f.write(f'Page: {page}\n')

    print(f'Processed page {page} / {max_pages}')
    page += 1

    # Now waiting until next_request_time
    wait_time = next_request_time - datetime.now()

    # If there is a positive amount of time remaining
    # Things can get screwy with negative time values without this check
    if wait_time > timedelta(seconds=0):
        sleep(wait_time.seconds + wait_time.microseconds / 1000000)
