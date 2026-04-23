import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from dataclasses import dataclass, field
import pandas as pd

BASE_URL = "https://books.toscrape.com/"

RATING_MAP = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

@dataclass
class Book:
    title: str = ""
    product_description: str = ""
    upc: str = ""
    rating: int = -1
    price: float = -1.0
    availability: str = ""
    number_of_reviews: int = -1

async def find_page_length(client: httpx.AsyncClient, url: str) -> int:
    """
    Test

    Args:
        client (httpx.AsyncClient): Asynchronous client from httpx module
        url (str): BASE_URL (books.toscrape.com)

    Returns:
        int: number of pages to scrape
    """
    response = await client.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    current_tag = soup.find("li", class_="current")
    if current_tag is None:
        return 1
    
    return int(current_tag.text.strip().split()[-1])

async def scrape_catalogue_page(client: httpx.AsyncClient, url: str) -> list[str]:
    """
    Scrape a single listing page & return absolute URLs for each book.

    Args:
        client (httpx.AsyncClient): Asynchronous client from httpx module
        url (str): BASE_URL (books.toscrape.com)

    Returns:
        list[str]: list of book's absolute URLs
    """
    response = await client.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # FIX
    book_urls = [
        urljoin(url, h3.find("a")["href"])
        for h3 in soup.find_all("h3")
    ]
    
    print("Book Catalogue Pages parsed.")
    return book_urls

async def fetch_book_html(client: httpx.AsyncClient, 
                          url: str,
                          semaphore: asyncio.Semaphore
                          ) -> str:
    async with semaphore:
        response = await client.get(url)
        return response.text

async def parse_book(html: str) -> Book:
    """
    Parse a single book detail page into a  Book dataclass

    Args:
        html (str): html tags for each book

    Returns:
        Book: Book data class
    """
    soup = BeautifulSoup(html, "html.parser")
    book = Book()

    # Title
    h1 = soup.find("h1")
    book.title = h1.text.strip() if h1 else ""

    # Description
    product_desc_header = soup.find("div", id="product_description")
    if product_desc_header:
        desc_p = product_desc_header.find_next_sibling("p")
        book.product_description = desc_p.text.strip() if desc_p else ""

    # Star Rating
    star_rating = soup.find("p", class_="star-rating")
    if star_rating:
        rating_word = star_rating["class"][1]
        book.rating = RATING_MAP.get(rating_word, -1)

    # Price
    price_tag = soup.find("p", class_="price_color")
    if price_tag:
        book.price = float(price_tag.text.strip().replace("£", ""))
    # Availability
    avail_tag = soup.find("p", class_="availability")
    book.availability = avail_tag.text.strip() if avail_tag else ""

    # UPC + number_of_reviews
    table = soup.find("table", class_="table-striped")
    if table:
        rows = {
            row.find("th").text.strip(): row.find("td").text.strip()
            for row in table.find_all("tr")
        }
        book.upc = rows.get("UPC", "")
        book.number_of_reviews = int(rows.get("Number of reviews", -1))
    
    return book

def save_to_csv(data: Book):
    pass


async def main():
    # TODO: add queue for worker to scrape 10-20 books at a time
    async with httpx.AsyncClient() as client:
        page_count = await find_page_length(client, BASE_URL)
        print(f"Total pages: {page_count}")

        catalogue_pages = [
            f"{BASE_URL}catalogue/page-{i}.html" 
            for i in range(1, page_count + 1)
        ]
        
        # the symbol * represent Python's list unpacking
        all_page_results = await asyncio.gather(
            *[scrape_catalogue_page(client, page_url) for page_url in catalogue_pages]
        )
        all_book_urls = [url for page in all_page_results for url in page]
        print(f"Total books found: {len(all_book_urls)}")

        # fetch all book detail pages concurrently
        semaphore = asyncio.Semaphore(20)
        all_html = await asyncio.gather(
            *[fetch_book_html(client, url, semaphore) for url in all_book_urls]
        )

        # parse each book
        books = await asyncio.gather(*[parse_book(html) for html in all_html])

    # Preview first 3 results
    for book in books[:3]:
        print("-" * 40)
        print(f"Title       : {book.title}")
        print(f"UPC         : {book.upc}")
        print(f"Rating      : {book.rating}/5")
        print(f"Price       : £{book.price}")
        print(f"Availability: {book.availability}")
        print(f"Reviews     : {book.number_of_reviews}")
        print(f"Description : {book.product_description[:80]}...")

    return books
 

if __name__ == "__main__":
    asyncio.run(main())
