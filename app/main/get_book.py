import requests
from bs4 import BeautifulSoup

# url = "https://www.litres.ru/search/?q=золотой+ключик"
url = "https://www.nsportal.ru"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 YaBrowser/25.2.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)

soup = BeautifulSoup(response.text, "lxml")

data = soup.find_all("span", class_="file")

for i in data:
    href_url = i.find("href")
    print(href_url)
