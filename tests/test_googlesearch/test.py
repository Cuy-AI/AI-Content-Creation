from components.Search.GoogleSearchEngine.GoogleSearchEngine import GoogleSearchEngine

def test_googlesearch():

    # Only 100 search queries per day for free
    client = GoogleSearchEngine()

    # Normal search --------------------------------------------------------------------------
    results = client.search("Python programming", num=5)

    print("Results of normal search:")
    for r in results: print(r)

    # Extract content
    info = client.extract_content(
        results[0]["link"], 
        ignore_tags=["script", "style", "footer", "nav"],
        required_tags=["title", "h1", "h2", "h3", "h4", "h5", "h6", "p"],
        only_required_tags=True
    )

    print("Extracted info:")
    print(info)

    # Image search --------------------------------------------------------------------------
    images = client.search("Cute cats", num=5, search_type="image")

    print("Images:")
    for img in images: print(img)

    # Downloads and saves with original extension
    saved_path = client.download_image(
        images[0]["link"],
        "volume/output/search_engine/cat_image"   # don’t need to pass extension
    )

    print("Image saved at:", saved_path)


    # Advanced search --------------------------------------------------------------------------

    print("Advanced search:")

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
