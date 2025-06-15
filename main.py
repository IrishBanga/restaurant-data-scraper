import os
import time
import json
import requests

# === Configuration ===

BASE_URL = "https://www.ubereats.com"
SEO_FEED_API = f"{BASE_URL}/_p/api/getSeoFeedV1?localeCode=ca"
PAGINATED_STORES_API = f"{BASE_URL}/_p/api/getPaginatedStoresV1?localeCode=ca"

DATA_DIR = "ubereats_data"
os.makedirs(DATA_DIR, exist_ok=True)

# Replace these placeholders with your actual session data
HEADERS = {
    "User-Agent": "<YOUR_USER_AGENT>",
    "Accept": "*/*",
    "Content-Type": "application/json",
    "Referer": "https://www.ubereats.com/ca/city/toronto-on",
    "Origin": "https://www.ubereats.com",
    "x-csrf-token": "<YOUR_CSRF_TOKEN>",
    "x-uber-client-gitref": "<YOUR_CLIENT_GITREF>",
}

COOKIES = {
    "uev2.id.xp": "<YOUR_UEV2_ID_XP>",
    "dId": "<YOUR_DID>",
    "uev2.id.session": "<YOUR_UEV2_ID_SESSION>",
    "uev2.ts.session": "<YOUR_UEV2_TS_SESSION>",
    "_ua": "<YOUR_UA>",
    "marketing_vistor_id": "<YOUR_MARKETING_VISITOR_ID>",
    "jwt-session": "<YOUR_JWT_SESSION>",
    # Add other cookies as needed
}

# === Master Category Lists (fill with your curated data) ===

MASTER_CUISINES = set(
    [
        # Add your cuisine strings here, all lowercase
    ]
)

MASTER_DIETARY_OPTIONS = set(
    [
        # Add your dietary options here, all lowercase
    ]
)

EXCLUSION_CATEGORIES = set(
    [
        # Add exclusion categories here, all lowercase
    ]
)

# === Business Hours Template ===

BUSINESS_HOURS_TEMPLATE = [
    {"day": "Monday", "opening": "09:00", "closing": "21:00"},
    {"day": "Tuesday", "opening": "09:00", "closing": "21:00"},
    {"day": "Wednesday", "opening": "09:00", "closing": "21:00"},
    {"day": "Thursday", "opening": "09:00", "closing": "21:00"},
    {"day": "Friday", "opening": "09:00", "closing": "22:00"},
    {"day": "Saturday", "opening": "10:00", "closing": "22:00"},
    {"day": "Sunday", "opening": "10:00", "closing": "20:00"},
]

# === Utility Functions ===


def save_json(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"Saved: {filepath}")


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_category(cat):
    return cat.strip().lower()


def parse_num_reviews(rating_count_str):
    if not rating_count_str:
        return 0
    cleaned = rating_count_str.replace(",", "").replace("+", "").strip()
    try:
        return int(cleaned)
    except ValueError:
        return 0


def should_exclude(categories):
    return any(normalize_category(cat) in EXCLUSION_CATEGORIES for cat in categories)


# === Step 1: Fetch Pages ===


def fetch_seo_feed():
    print("Fetching SEO feed (page 1)...")
    response = requests.post(SEO_FEED_API, headers=HEADERS, cookies=COOKIES, json={})
    if response.status_code == 200:
        filepath = os.path.join(DATA_DIR, "page_1.json")
        save_json(response.json(), filepath)
    else:
        raise Exception(
            f"Failed to fetch SEO feed: {response.status_code} {response.text}"
        )


def fetch_paginated_page(page_num, city_slug="toronto-on", category=""):
    print(f"Fetching paginated page {page_num}...")
    payload = {"citySlug": city_slug, "category": category, "pageNumber": page_num}
    headers = HEADERS.copy()
    headers["Referer"] = f"https://www.ubereats.com/ca/city/{city_slug}?page={page_num}"
    response = requests.post(
        PAGINATED_STORES_API, headers=headers, cookies=COOKIES, json=payload
    )
    if response.status_code == 200:
        filepath = os.path.join(DATA_DIR, f"page_{page_num}.json")
        save_json(response.json(), filepath)
    else:
        raise Exception(
            f"Failed to fetch page {page_num}: {response.status_code} {response.text}"
        )


def fetch_all_pages(max_pages=20, delay=2):
    fetch_seo_feed()
    time.sleep(delay)
    for page in range(2, max_pages + 1):
        fetch_paginated_page(page)
        time.sleep(delay)


# === Step 2: Consolidate StoresMap ===


def consolidate_stores_map():
    combined_stores = {}
    files = sorted(
        [
            f
            for f in os.listdir(DATA_DIR)
            if f.startswith("page_") and f.endswith(".json")
        ]
    )
    print(f"Consolidating {len(files)} files...")
    for filename in files:
        filepath = os.path.join(DATA_DIR, filename)
        data = load_json(filepath)
        if (
            data.get("status") == "success"
            and "data" in data
            and "storesMap" in data["data"]
        ):
            combined_stores.update(data["data"]["storesMap"])
        else:
            print(f"Warning: Missing storesMap in {filename}")
    combined_filepath = os.path.join(DATA_DIR, "combined_storesMap.json")
    save_json(combined_stores, combined_filepath)
    return combined_filepath


# === Step 3: Clean Unwanted Fields ===

REMOVE_KEYS = [
    "heroImage",
    "etaRange",
    "fareBadge",
    "promotion",
    "isOpen",
    "closedMessage",
    "endorsement",
    "promoTrackings",
    "attributeBadgeList",
    "modalities",
]


def clean_data(input_file):
    stores = load_json(input_file)
    cleaned = {}
    for uuid, data in stores.items():
        cleaned[uuid] = {k: v for k, v in data.items() if k not in REMOVE_KEYS}
    cleaned_filepath = os.path.join(DATA_DIR, "cleaned_storesMap.json")
    save_json(cleaned, cleaned_filepath)
    return cleaned_filepath


# === Step 4: Transform data for Mongoose Schema ===


def transform_restaurant(uuid, data):
    name = data.get("title", "")
    meta = data.get("meta", {})
    categories = meta.get("categories", [])
    cuisines = categories  # Will filter later
    dietary_options = categories  # Will filter later

    rating_info = data.get("rating", {}).get("feedback", {})
    rating = rating_info.get("rating", 0.0)
    num_reviews = parse_num_reviews(rating_info.get("ratingCount", ""))

    price_range = meta.get("priceBucket", "")

    location = data.get("location", {}).get("formattedAddress", "")

    banner_images = []
    hero_image_url = data.get("heroImageUrl")
    if hero_image_url:
        banner_images.append({"url": hero_image_url})

    return {
        "name": name,
        "cuisines": cuisines,
        "rating": rating,
        "numReviews": num_reviews,
        "priceRange": price_range,
        "dietaryOptions": dietary_options,
        "businessHours": BUSINESS_HOURS_TEMPLATE,
        "bannerImages": banner_images,
        "images": [],
        "location": location,
    }


def transform_all(input_file):
    stores = load_json(input_file)
    transformed = []
    for uuid, data in stores.items():
        transformed.append(transform_restaurant(uuid, data))
    transformed_filepath = os.path.join(DATA_DIR, "restaurants_for_mongoose.json")
    save_json(transformed, transformed_filepath)
    return transformed_filepath


# === Step 5: Filter Categories and Exclude Restaurants ===


def filter_restaurants(input_file):
    data = load_json(input_file)
    filtered = []
    excluded_count = 0

    for rest in data:
        combined_cats = set(
            [
                normalize_category(c)
                for c in rest.get("cuisines", []) + rest.get("dietaryOptions", [])
            ]
        )
        if should_exclude(combined_cats):
            excluded_count += 1
            continue

        rest["cuisines"] = [
            c
            for c in rest.get("cuisines", [])
            if normalize_category(c) in MASTER_CUISINES
        ]
        rest["dietaryOptions"] = [
            d
            for d in rest.get("dietaryOptions", [])
            if normalize_category(d) in MASTER_DIETARY_OPTIONS
        ]

        filtered.append(rest)

    print(f"Excluded {excluded_count} restaurants based on exclusion categories.")
    print(f"Remaining restaurants: {len(filtered)}")

    filtered_filepath = os.path.join(DATA_DIR, "restaurants_filtered.json")
    save_json(filtered, filtered_filepath)
    return filtered_filepath


# === Main Workflow ===


def main(max_pages=20, delay=2):
    print("=== Starting Uber Eats Scraping Workflow ===")
    fetch_all_pages(max_pages=max_pages, delay=delay)
    combined_file = consolidate_stores_map()
    cleaned_file = clean_data(combined_file)
    transformed_file = transform_all(cleaned_file)
    filtered_file = filter_restaurants(transformed_file)
    print(f"Workflow complete. Final data file: {filtered_file}")


if __name__ == "__main__":
    main()
