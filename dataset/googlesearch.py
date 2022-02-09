from googleapiclient.discovery import build
from bs4 import BeautifulSoup
import json

QUERY = ('"deaf" OR "hard-of-hearing" OR "hard of hearing" OR "sign language" '
         'OR "cochlear implant" OR "hearing impaired" -"tone deaf" -"deaf ears" -"deaf ear"')
ARTICLES_PER_PAGE = 10

# Our API key
with open('./ggl_api.key') as f:
    api_key = f.read().strip()

# A JSON file containing our custom search engine keys
# A requirement for using the Custom Search API unfortunately
with open('cx.json') as f:
    cx = json.load(f)

# The base function we're using to pull data from the Custom Search API
def query(site, year, start, year_delta=1, start_month='01', end_month='12', **kwargs):
    # Retrieving our custom search engine code
    cse_id = cx[site]

    # While the parameter may be called sort, we're actually using it
    #   to filter our data, specifically by date
    sort_str = f'date:r:{year}{start_month}01:{year + year_delta - 1}{end_month}31'

    # Using the google library to make the API call
    with build("customsearch", "v1", developerKey=api_key) as service:
        results = service.cse().list(q=QUERY,
                                     cx=cse_id,
                                     sort=sort_str,
                                     start=start,
                                     **kwargs
                                     ).execute()

    totalArticles = 0
    if results and 'searchInformation' in results and 'totalResults' in results['searchInformation']:
        totalArticles = int(results['searchInformation']['totalResults'])
    
    articles = []
    if 'items' in results:
        for article in results['items']:
            metadata = {}

            if 'link' in article:
                metadata['url'] = article['link']
            else:
                # If we can't find a link, we may as well skip
                continue

            if 'title' in article:
                metadata['headline'] = article['title']
            
            # This part is really weird. Google stores some data in a buried list
            # So first we uncover whether the list exists, and then iterate through it
            # I've only seen the list have a single element, but better safe than sorry
            if 'pagemap' in article and 'metatags' in article['pagemap']:
                for tag in article['pagemap']['metatags']:
                    # Could alternatively consider using 'article:modified_time'
                    if 'article:published_time' in tag:
                        metadata['date'] = tag['article:published_time']
            
            metadata['source'] = site

            articles.append(metadata)
    else:
        totalArticles = 0
    
    return totalArticles, articles
