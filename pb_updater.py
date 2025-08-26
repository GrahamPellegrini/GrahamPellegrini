#!/usr/bin/env python3
"""
Personal Best Tracker - Automated README Updater

This script scrapes athletics personal best times from OpenTrack and updates
the Personal Best Tracker section in README.md. It combines scraped data
with confirmed national records to ensure accuracy.

Author: Graham Pellegrini
Last Updated: August 2025
"""

from pathlib import Path
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Configuration
OPENTRACK_URL = "https://malta.opentrack.run/en-gb/a/f77598db-2a2a-4597-a0d1-0ee86eda6147/#pills-performance/"
TARGET_EVENTS = ["60", "100", "200", "300", "400"]

# National records that should override scraped data
CONFIRMED_RECORDS = {
    "200m": "21.18s",  # U20/U23/Open National Record (April 2023)
    "300m": "34.42s",  # U20 National Record (February 2023)
    "400m": "46.83s"   # U20/U23/Open National Record (June 2023)
}

# Event display order in README
EVENT_ORDER = ["60m", "100m", "200m", "300m", "400m", "800m", "1500m"]

def setup_webdriver():
    """Configure and return a headless Chrome WebDriver."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)

def find_pb_tab(driver):
    """Locate and click the Personal Best tab on OpenTrack."""
    print("Looking for PB tab...")
    
    # Multiple selectors to try for finding the PB tab
    selectors = [
        "//button[contains(text(), 'PB')]",
        "//a[contains(text(), 'PB')]", 
        "//*[contains(text(), 'Personal Best')]",
        "//*[contains(text(), 'PB')]"
    ]
    
    for selector in selectors:
        try:
            pb_tab = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, selector))
            )
            print("Found PB tab")
            pb_tab.click()
            time.sleep(3)  # Allow content to load
            return True
        except TimeoutException:
            continue
    
    print("Could not find PB tab, proceeding with default view...")
    return False

def parse_time(time_text):
    """
    Parse a time string, handling wind readings in parentheses.
    
    Args:
        time_text (str): Raw time text (e.g., "10.72 (+3.3)" or "21.18")
    
    Returns:
        str or None: Cleaned time string or None if invalid
    """
    time_clean = time_text.split('(')[0].strip()  # Remove wind reading
    
    # Validate time format (decimal number between 4-8 characters)
    if ("." in time_clean and 
        len(time_clean) >= 4 and len(time_clean) <= 8 and
        time_clean.replace(".", "").replace(":", "").isdigit()):
        return time_clean
    
    return None

def extract_times_from_tables(soup):
    """
    Extract personal best times from OpenTrack result tables.
    
    Args:
        soup (BeautifulSoup): Parsed HTML content
    
    Returns:
        dict: Event names mapped to personal best times
    """
    pb_dict = {}
    tables = soup.find_all("table")
    print(f"Found {len(tables)} tables on page")
    
    for table in tables:
        # Look for performance/result tables
        table_classes = str(table.get("class", [])).lower()
        if "performance" in table_classes or "result" in table_classes:
            rows = table.find_all("tr")[1:]  # Skip header row
            
            for row in rows:
                cols = row.find_all(["td", "th"])
                if len(cols) < 3:
                    continue
                
                # Look for event number in first 3 columns
                event_col = None
                event_name = None
                
                for i, col in enumerate(cols[:3]):
                    text = col.text.strip()
                    if text in TARGET_EVENTS:
                        event_col = i
                        event_name = text
                        break
                
                if event_col is None:
                    continue
                
                # Look for time in columns after the event
                for j in range(event_col + 1, len(cols)):
                    time_text = cols[j].text.strip()
                    parsed_time = parse_time(time_text)
                    
                    if parsed_time:
                        event_key = f"{event_name}m"
                        
                        # Keep the best (fastest) time for each event
                        if (event_key not in pb_dict or 
                            float(parsed_time) < float(pb_dict[event_key].replace("s", ""))):
                            pb_dict[event_key] = parsed_time + ("s" if not parsed_time.endswith("s") else "")
                            print(f"Found: {event_key} -> {pb_dict[event_key]}")
                        break
    
    return pb_dict

def scrape_opentrack():
    """
    Scrape personal best times from OpenTrack website.
    
    Returns:
        dict: Event names mapped to personal best times
    """
    driver = setup_webdriver()
    
    try:
        print("Loading OpenTrack page...")
        driver.get(OPENTRACK_URL)
        time.sleep(3)
        
        # Try to click PB tab
        find_pb_tab(driver)
        
        # Parse the page content
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        pb_dict = extract_times_from_tables(soup)
        
        if not pb_dict:
            print("No times found, using fallback data...")
            return {
                "200m": "21.18s",
                "300m": "34.42s", 
                "400m": "46.83s"
            }
        
        print(f"Extracted {len(pb_dict)} personal bests")
        return pb_dict
        
    except Exception as e:
        print(f"Error scraping OpenTrack: {e}")
        # Return fallback data on error
        return {
            "200m": "21.18s",
            "300m": "34.42s", 
            "400m": "46.83s"
        }
    finally:
        driver.quit()

def build_widget(scraped_pbs):
    """
    Build the README widget content from scraped and confirmed personal bests.
    
    Args:
        scraped_pbs (dict): Personal bests scraped from OpenTrack
    
    Returns:
        str: Formatted markdown table for README
    """
    lines = []
    lines.append("### Personal Best Tracker\n")
    lines.append("| Event | PB |")
    lines.append("|-------|-----|")
    
    # Merge scraped data with confirmed records (confirmed takes priority)
    final_pbs = {}
    final_pbs.update(scraped_pbs)      # Start with scraped data
    final_pbs.update(CONFIRMED_RECORDS)  # Override with confirmed records
    
    # Add events in preferred order
    for event in EVENT_ORDER:
        if event in final_pbs:
            lines.append(f"| {event} | {final_pbs[event]} |")
    
    # Add any additional events not in standard order
    for event in sorted(final_pbs.keys()):
        if event not in EVENT_ORDER:
            lines.append(f"| {event} | {final_pbs[event]} |")
    
    lines.append("\n> _Sourced from [OpenTrack](https://malta.opentrack.run/)_")
    return "\n".join(lines)

def update_readme(widget_content):
    """
    Update the Personal Best Tracker section in README.md.
    
    Args:
        widget_content (str): New content for the PB section
    """
    readme_path = Path("README.md")
    
    if not readme_path.exists():
        print("README.md not found.")
        return
    
    content = readme_path.read_text()
    start_tag = "<!-- START_PB -->"
    end_tag = "<!-- END_PB -->"
    
    if start_tag not in content or end_tag not in content:
        print("START/END tags not found in README.md.")
        return
    
    # Replace content between tags
    before = content.split(start_tag)[0]
    after = content.split(end_tag)[1]
    updated_content = f"{before}{start_tag}\n{widget_content}\n{end_tag}{after}"
    
    readme_path.write_text(updated_content)
    print("README.md updated with new PB section.")

def main():
    """Main execution function."""
    print("Starting Personal Best Tracker update...")
    
    # Scrape latest times from OpenTrack
    scraped_times = scrape_opentrack()
    
    # Build the README widget
    widget_content = build_widget(scraped_times)
    
    # Save widget to file (for debugging/backup)
    Path("pb_widget.md").write_text(widget_content)
    
    # Update README.md
    update_readme(widget_content)
    
    print("Personal Best Tracker update complete!")

if __name__ == "__main__":
    main()
