import asyncio
import httpx
from bs4 import BeautifulSoup


async def find_page_length(client, url):
    response = await client.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    page_len = str(soup.find("li", class_="current")).split()[5]
    # print(page_len)

    return page_len

async def scrape_book_store(client, url):
    response = await client.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.find("h1")
    book_paginations = list(soup.find_all("h3"))
    parsed_book_catalogues = [str(book_pagination).split()[1].split('"')[1]
                               for book_pagination in book_paginations]
    
    print(f"title: {title}")
    print(f"books: {parsed_book_catalogues}")
    
    return parsed_book_catalogues

async def scrape_book(client, url, catalogues):
    book_responses = {}
    
    for catalogue in catalogues:
        response = await client.get(url + catalogue)
        book_responses[str(catalogue)] = response.text
    
    return book_responses
        

async def parse_data(response):
    book_details = {}
    # FIXME: trying to figure it out what parameter to use on this func()
    soup = BeautifulSoup(response.text, "html.parser")
    for book in books:
        book_details["title"] = ""
        book_details["product_description"] = ""
        book_details["upc"] = ""
        book_details["rating"] = -1
        book_details["price"] = -1
        book_details["availability"] = True
        book_details["number_of_reviews"] = -1
    
    
    
async def main():
    # TODO: add full functional programming here
    url = "https://books.toscrape.com"
    # response = requests.get(url)
    # with httpx.AsyncClient() as client:
    #     page_len = find_page_length(response=client, url=url)
    #     for page_number in range(1, page_len + 1):
    #         pagination = f"catalogue/page-{page_number}.html"
    #         scrape_book_store(client, url=url+pagination)
    
    async with httpx.AsyncClient() as client:
        book_catalogues = await scrape_book_store(client, url)
        

if __name__ == "__main__":
    asyncio.run(main())
