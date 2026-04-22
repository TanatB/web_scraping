import httpx, requests
from bs4 import BeautifulSoup


def scrape_book_store(response):
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.find("h1")

    books = soup.find_all("article", class_="product_pod")
    
    print(f"title: {title}")
    print(f"books: {len(books)}")

def main():
    url = "https://books.toscrape.com"
    response = requests.get(url)

    print(f"status: {response.status_code}")
    print("=" * 50)

    scrape_book_store(response=response)

if __name__ == "__main__":
    main()
