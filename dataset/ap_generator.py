from googlesearch import query, ARTICLES_PER_PAGE
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from time import sleep
from os import path
import grequests
import json


def ap_query(date, start, **kwargs):
    return query("AP News", date, start, **kwargs)

def ap_scraper(html):
    soup = BeautifulSoup(html, 'html5lib')

    content = soup.find('div', {'class': 'Article'})
    date = soup.find('span', {'class':'Timestamp'})

    content = content.text if content else ''
    date = date.get('data-source')

    return date, content

# In case we halt our queries early, we can resume part way through
start_date = int(input('Starting date: '))
start_count = int(input('Starting count: '))
max_requests = int(input('Max number of requests to make: '))

# Retrieving what data we have so far
data = []
if path.exists('./ap_data.json'):
    with open('./ap_data.json', 'r') as f:
        data = json.load(f)

# Which date is currently being searched
date = start_date

# Used to determine when to stop looking back in time
# When a year pulls up no results, we stop searching
article_delta = 0

# Making sure we don't go over the limit of the number of requests we can make
requests = 0

# Count determines which page of the current year we're in
count = max(start_count, 1)
max_count = count
while requests < max_requests:
    # We can't go above count 100 becase of the API
    # We'll just have to miss the articles above that amount
    while count <= max_count and count < 100 and requests < max_requests:
        # We can make requests a lot faster than this
        # But we really don't need to
        # We only have a max of 100 requests anyway
        next_request_time = datetime.now() + timedelta(seconds=3)

        max_count, articles = ap_query(date, count)
        article_delta += len(articles)
        requests += 1
            
        # Now we can concurrently scrape all the articles
        # This is where grequests comes in useful
        # This is much faster than individually scraping them
        urls = [m['url'] for m in articles]
        rqs = (grequests.get(u) for u in urls)
        responses = grequests.map(rqs)

        # Now we can scrape the HTML for the relevant text
        for r, m in zip(responses, articles):
            if r:
                m['date'], m['text'] = ap_scraper(r.content)
                if m['text'] == '' or m['date'] == '':
                    print(f'Failed to scrape')
                    m['error'] = 'Failed to scrape'
            else:
                print(f'Request failed for {m["url"]}')
                m['error'] = str(r)

        # Writing the data to our file
        data += articles
        with open('./ap_data.json', 'w') as f:
            json.dump(data, f)
        
        # We can also write the page to a file, just in case of crashes
        #   it'll allow for an easy continuation later
        with open('./ap_data_page.txt', 'w') as f:
            f.write(f'Date: {date}\nCount: {count}\nRequests: {requests}\n')

        print(f'Processed count {count}, requests: {requests} / {max_requests}')
        count += ARTICLES_PER_PAGE

        # Now waiting until next_request_time
        wait_time = next_request_time - datetime.now()

        # If there is a positive amount of time remaining
        # Things can get screwy with negative time values without this check
        if wait_time > timedelta(seconds=0):
            sleep(wait_time.seconds + wait_time.microseconds / 1000000)
    
    if count >= 100:
        print(f"Couldn't complete year {date} due to hitting count limit. {max_count=}")
    
    # We have found all the articles for the current year
    print(f'Processed year {date}, articles found: {article_delta}')

    if requests >= max_requests:
        print(f'Halted due to reaching request maximum: {requests} / {max_requests}')
        break

    # # If there were none, we can wrap up the search
    # if article_delta == 0:
    #     print('Halted due to no articles being found for the processed year')
    #     break

    date -= 1
    count = 1
    max_count = 1
    article_delta = 0
