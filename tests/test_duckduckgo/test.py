from components.Search.DuckDuckGoSearch.DuckDuckGoSearch import DuckDuckGoSearch

def print_results(header: str, results: list):
    print(header)
    for r in results:
        print("Result:")
        for k, v in r.items():
            print(f"\t{k} -> {v}")
    print("\n" + "=" * 60 + "\n")

def test_duckduckgo():

    searcher = DuckDuckGoSearch(rate_limit=3.0)

    # --- WEB TESTS (3) ---
    # Test 1: general query (default params)
    try:
        results = searcher.search_web("latest AI research papers", num_results=5)
        print_results("Web Results - Test 1: 'latest AI research papers' (default)", results)
    except Exception as e:
        print("Web Test 1 failed:", e)

    # Test 2: google-hack style - limit to a domain and filetype (site: + filetype:)
    # This emulates "site:arxiv.org 'deep learning' filetype:pdf"
    try:
        q2 = "site:arxiv.org \"deep learning\" filetype:pdf"
        results = searcher.search_web(q2, num_results=5, safesearch="off", region="wt-wt")
        print_results(f"Web Results - Test 2: '{q2}' (site + filetype)", results)
    except Exception as e:
        print("Web Test 2 failed:", e)

    # Test 3: intitle + inurl (search for surveys & reviews)
    # Example: intitle:"survey" "machine learning" inurl:review
    try:
        q3 = 'intitle:"survey" "machine learning" inurl:review'
        results = searcher.search_web(q3, num_results=5, safesearch="moderate", time_range="y")
        print_results(f"Web Results - Test 3: '{q3}' (intitle + inurl + past year)", results)
    except Exception as e:
        print("Web Test 3 failed:", e)

    # --- IMAGE TESTS (3) ---
    # Image Test 1: general image query (default)
    try:
        images = searcher.search_images("golden retriever puppy", num_results=5)
        print_results("Image Results - Test 1: 'golden retriever puppy' (default)", images)
    except Exception as e:
        print("Image Test 1 failed:", e)

    # Image Test 2: filtered images - large photos (satellite)
    try:
        q_img2 = "satellite view of lima peru"
        images = searcher.search_images(q_img2, num_results=5, size="Large", type_image="photo")
        print_results(f"Image Results - Test 2: '{q_img2}' (Large, photo)", images)
    except Exception as e:
        print("Image Test 2 failed:", e)

    # Image Test 3: logo / transparent background / monochrome or clipart
    try:
        q_img3 = 'logo "openai"'
        images = searcher.search_images(q_img3, num_results=5, type_image="transparent", color="Monochrome", safesearch="on")
        print_results(f"Image Results - Test 3: '{q_img3}' (transparent, monochrome, strict safe)", images)
    except Exception as e:
        print("Image Test 3 failed:", e)
