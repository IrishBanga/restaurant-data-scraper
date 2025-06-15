# restaurant-data-scraper

## Overview
This document describes the end-to-end process of scraping restaurant data from Uber Eats for Toronto using Python. The approach leverages Uber Eats’ internal APIs by simulating actual web client requests, including all required headers and authentication tokens, to retrieve structured JSON data. The data is then consolidated, cleaned, transformed, and prepared for MongoDB import.


## Process Summary

### 1. Simulating API Requests
- Identified two main internal APIs:
  - `getSeoFeedV1` — retrieves the first page of restaurant data.
  - `getPaginatedStoresV1` — retrieves subsequent pages.
- Both APIs require **POST** requests with specific headers and cookies to succeed.
- Pagination is handled by incrementing the `pageNumber` in the payload for `getPaginatedStoresV1`.


### 2. Request Headers and Authentication
To successfully call these APIs, the following headers must be included with valid values extracted from an authenticated browser session:

```python
HEADERS = {
    "User-Agent": "",
    "Accept": "*/*",
    "Content-Type": "application/json",
    "Referer": "https://www.ubereats.com/ca/city/toronto-on",
    "Origin": "https://www.ubereats.com",
    "x-csrf-token": "",
    "x-uber-client-gitref": "",
    "Cookie": ""
}
```

- **User-Agent**: Browser user agent string.
- **Referer** and **Origin**: URLs indicating request origin.
- **x-csrf-token**: CSRF token for request validation.
- **x-uber-client-gitref**: Client version identifier.
- **Cookie**: Session and authentication cookies.


### 3. Request Payloads

- **First page (`getSeoFeedV1`)**:

```json
{}
```

- **Subsequent pages (`getPaginatedStoresV1`)**:

```json
{
  "citySlug": "toronto-on",
  "category": "",
  "pageNumber": 
}
```


### 4. Data Saving and Pagination
- Each API response is saved as a separate JSON file (e.g., `page_1.json`, `page_2.json`).
- Pagination is handled by incrementing the `pageNumber` in the payload until all pages are fetched or a limit is reached.
- Delays between requests are used to avoid rate limiting.


### 5. Data Consolidation and Cleaning
- All JSON files are combined by merging their `storesMap` objects keyed by restaurant UUID.
- Unnecessary fields such as `heroImage`, `etaRange`, `fareBadge`, `promotion`, `isOpen`, `closedMessage`, `endorsement`, `promoTrackings`, `attributeBadgeList`, and `modalities` are removed to clean the data.


### 6. Data Transformation
- The cleaned data is transformed to match a Mongoose schema for MongoDB:
  - `title` → `name`
  - `meta.categories` → `cuisines` and temporarily also `dietaryOptions`
  - `rating.feedback.rating` → `rating` (float)
  - `rating.feedback.ratingCount` → `numReviews` (integer parsed from strings like "3,000+")
  - `meta.priceBucket` → `priceRange`
  - `location.formattedAddress` → `location`
  - `heroImageUrl` → `bannerImages` array
  - `images` left empty (can be added later)
  - `businessHours` set to a fixed template as original data lacks this


### 7. Category Filtering
- Categories are split into master lists for **cuisines** and **dietary options**. You can define these lists based on your requirements.
- A third **exclusion list** to define non-restaurant or irrelevant categories (e.g., "Convenience", "Grocery", etc.).
- Restaurants containing any exclusion categories are filtered out.
- Remaining restaurants have their `cuisines` and `dietaryOptions` trimmed to only include valid master categories.


## Important Notes
- Valid cookies and CSRF tokens must be extracted from an authenticated browser session (e.g., via browser DevTools or Selenium).
- Use polite delays between requests to avoid being blocked.
- Always respect Uber Eats’ terms of service and legal considerations.
- The internal APIs are undocumented and may change; so this process may require adjustments in the future.