from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from pathlib import Path

OT_URL = "https://malta.opentrack.run/en-gb/a/f77598db-2a2a-4597-a0d1-0ee86eda6147/#pills-performance/"

options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")

driver = webdriver.Chrome(options=options)
driver.get(OT_URL)

# Wait a bit to allow full JS load
import time
time.sleep(5)

html = driver.page_source
Path("opentrack_dump.html").write_text(html)
print("✅ Dump saved to opentrack_dump.html")

driver.quit()
