from components.Search.GoogleSearchEngine.GoogleSearchEngine import GoogleSearchEngine

def test_googlesearch():

    # Only 100 search queries per day for free
    client = GoogleSearchEngine()

    # Normal search --------------------------------------------------------------------------
    results = client.search("Python programming", num=5)
    for r in results: print(r)

    # Image search --------------------------------------------------------------------------
    images = client.search("Cute cats", num=5, search_type="image")
    for img in images: print(img)


    # Advanced search --------------------------------------------------------------------------

    # Search excluding a site
    results = client.search("Python tutorial", siteSearch="wikipedia.org", siteSearchFilter="e")
    for r in results: print(r)

    # Search biased to Peru (country code "pe"), Spanish interface
    results = client.search("Noticias de tecnología", gl="pe", hl="es")
    for r in results: print(r)

    # Search only PDFs
    results = client.search("machine learning", fileType="pdf")
    for r in results: print(r)

    # Image search with safe mode on
    images = client.search("cats", search_type="image", safe="active")
    for r in results: print(r)
