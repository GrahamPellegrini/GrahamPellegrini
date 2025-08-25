from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# URL of your OpenTrack profile
OT_URL = "https://malta.opentrack.run/en-gb/a/f77598db-2a2a-4597-a0d1-0ee86eda6147/#pills-performance/"

# Events of interest
EVENTS = ["60", "100", "200", "300", "400"]
EVENT_ALIASES = {
    "60": "60m",
    "100": "100m",
    "200": "200m",
    "300": "300m",
    "400": "400m"
}

def scrape_opentrack():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=options)
    driver.get(OT_URL)

    try:
        # Wait for and click the PB tab
        pb_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'PB')]"))
        )
        pb_tab.click()
        time.sleep(2)  # allow time for table to render

        # Now parse page with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        pb_section = soup.find("div", id="perf-tab-PB")
        pb_table = pb_section.find("table", class_="performances-table")
        pb_dict = {}

        if pb_table:
            rows = pb_table.find_all("tr")[1:]  # Skip header row
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 3:
                    event = cols[1].text.strip()
                    result = cols[2].text.strip()
                    if event in EVENT_ALIASES:
                        pb_dict[EVENT_ALIASES[event]] = result
                    else:
                        pb_dict[event] = result

        return pb_dict

    except Exception as e:
        print("❌ Error scraping OpenTrack:", e)
        return {}

    finally:
        driver.quit()


def build_widget(pbs):
    lines = []
    lines.append("### Personal Best Tracker\n")
    lines.append("| Event | PB |")
    lines.append("|-------|-----|")
    for event in sorted(pbs):
        lines.append(f"| {event} | {pbs[event]} |")
    lines.append("\n> _Sourced from [OpenTrack](https://malta.opentrack.run/)_")
    return "\n".join(lines)

def update_readme(widget_text):
    readme_path = Path("README.md")
    if not readme_path.exists():
        print("❌ README.md not found.")
        return

    content = readme_path.read_text()
    start_tag = "<!-- START_PB -->"
    end_tag = "<!-- END_PB -->"

    if start_tag not in content or end_tag not in content:
        print("❌ START/END tags not found in README.md.")
        return

    before = content.split(start_tag)[0]
    after = content.split(end_tag)[1]
    new_block = f"{start_tag}\n{widget_text}\n{end_tag}"

    updated = before + new_block + after
    readme_path.write_text(updated)
    print("✅ README.md updated with new PB section.")

def main():
    ot_pb = scrape_opentrack()
    widget = build_widget(ot_pb)
    Path("pb_widget.md").write_text(widget)
    update_readme(widget)

if __name__ == "__main__":
    main()
