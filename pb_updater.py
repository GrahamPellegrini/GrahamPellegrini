#!/usr/bin/env python3
"""
Personal Best Tracker - Automated README Updater

This script scrapes athletics personal best times from OpenTrack and World Athletics,
handling both indoor and outdoor times. It automatically detects national records and
updates the Personal Best Tracker section in README.md.

Author: Graham Pellegrini
Last Updated: February 2026
"""

from pathlib import Path
import time
import json
import random
import re
import os
from datetime import datetime
from typing import Dict, Tuple, Optional
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin

# Optional: Playwright for Cloudflare bypass
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Configuration
OPENTRACK_URL = "https://malta.opentrack.run/en-gb/a/f77598db-2a2a-4597-a0d1-0ee86eda6147/"
WORLD_ATHLETICS_URL = "https://worldathletics.org/athletes/malta/graham-pellegrini-14962811"

# Standard event distances (in meters)
TARGET_EVENTS = ["60", "100", "200", "300", "400", "800", "1500"]

# National records information
# Format: "event": {"time": "time_value", "date": "YYYY-MM-DD", "location": "location"}
NATIONAL_RECORDS = {
    "200m": {"time": "21.18s", "date": "2023-04-01", "location": "Malta National Record"},
    "300m": {"time": "34.42s", "date": "2023-02-01", "location": "U20 National Record"}
}

# Personal bests to use when scraping fails (actual times, not all NRs)
FALLBACK_TIMES = {
    "60m": "6.04s",
    "60m SH": "6.08s",
    "100m": "10.93s",
    "200m": "21.18s",  # This IS a NR
    "300m": "34.76s",
    "400m": "46.83s",  # No longer NR
    "200m SH": "21.83s"
}

# Event display order in README
EVENT_ORDER = ["60m", "100m", "200m", "300m", "400m", "800m", "1500m"]


class AthleteicsDataScraper:
    """Scraper for athletics personal best data from multiple sources."""
    
    def __init__(self):
        self.session = requests.Session()
        self._world_athletics_records = {}  # Store NR info from World Athletics
        # Multiple user agents to avoid detection
        self.user_agents = [
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        self._setup_session()
    
    def _setup_session(self):
        """Configure session with headers to avoid bot detection."""
        import random
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        self.session.headers.update(headers)
    
    def _fetch_with_playwright(self, url: str) -> Optional[str]:
        """
        Fetch URL using Playwright (handles Cloudflare challenges).
        Uses browser automation to bypass Cloudflare and render dynamic content.
        
        Args:
            url: URL to fetch
        
        Returns:
            HTML content or None if fetch failed
        """
        if not PLAYWRIGHT_AVAILABLE:
            return None
        
        try:
            print(f"  Using Playwright to bypass Cloudflare...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US'
                )
                
                page = context.new_page()
                page.set_extra_http_headers({
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                })
                
                # Navigate and wait for page to be interactive
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                
                # Wait for JS to render data (5 seconds should be enough for Vue/React)
                page.wait_for_timeout(5000)
                
                content = page.content()
                context.close()
                browser.close()
                
                if content and len(content) > 500:
                    return content
                    
        except Exception as e:
            error_msg = str(e)[:150]
            if 'timeout' in error_msg.lower():
                print(f"  Playwright timeout")
            else:
                print(f"  Playwright error: {error_msg}")
        
        return None
    
    def _fetch_with_retry(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """
        Fetch URL with retry logic and exponential backoff.
        
        Args:
            url: URL to fetch
            max_retries: Number of retries on failure
        
        Returns:
            Response object or None if all retries failed
        """
        import random
        
        for attempt in range(max_retries):
            try:
                # Rotate user agent
                self.session.headers['User-Agent'] = random.choice(self.user_agents)
                
                # Add random delay to appear more human-like
                if attempt > 0:
                    time.sleep(random.uniform(2, 5))
                
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                print(f"  Attempt {attempt + 1} failed: {str(e)[:100]}")
                if attempt == max_retries - 1:
                    print(f"  Failed to fetch {url} after {max_retries} attempts")
                    return None
        
        return None
    
    def parse_time(self, time_text: str) -> Optional[str]:
        """
        Parse a time string, handling wind readings and formatting.
        
        Args:
            time_text (str): Raw time text (e.g., "10.72 (+3.3)" or "21.18")
        
        Returns:
            Optional[str]: Cleaned time string or None if invalid
        """
        if not time_text or not isinstance(time_text, str):
            return None
        
        # Remove wind reading and extra whitespace
        time_clean = time_text.split('(')[0].strip()
        
        # Handle time format variations
        if time_clean:
            # Check for valid time format
            components = time_clean.replace(":", ".").split(".")
            if len(components) >= 2:
                try:
                    # Try to parse as a number
                    float(time_clean.replace(":", ""))
                    if not time_clean.endswith("s"):
                        time_clean += "s"
                    return time_clean
                except (ValueError, AttributeError):
                    pass
        
        return None
    
    def scrape_opentrack(self) -> Dict[str, str]:
        """
        Scrape personal best times from OpenTrack website.
        Returns times with variant labels (e.g., "100m", "200m SH" for indoor).
        
        If scraping fails, checks for OPENTRACK_PBS environment variable with JSON-encoded times.
        Example: OPENTRACK_PBS='{"200m": "21.18s", "200m SH": "21.83s"}'
        
        Returns:
            Dict with format: "event_variant": "time" (e.g., {"100m": "10.72s", "200m SH": "20.50s"})
        """
        print("Scraping OpenTrack...")
        pbs = {}
        
        # Check for manual entry via environment variable (useful when Cloudflare blocks scraping)
        env_times = os.getenv('OPENTRACK_PBS')
        if env_times:
            try:
                pbs = json.loads(env_times)
                print(f"  Loaded {len(pbs)} times from OPENTRACK_PBS environment variable")
                return pbs
            except json.JSONDecodeError:
                print(f"  Warning: OPENTRACK_PBS is invalid JSON, attempting web scrape...")
        
        # First try with requests
        response = self._fetch_with_retry(OPENTRACK_URL)
        
        # If requests fails, try Playwright to bypass Cloudflare
        if not response:
            if PLAYWRIGHT_AVAILABLE:
                content = self._fetch_with_playwright(OPENTRACK_URL)
                if content:
                    soup = BeautifulSoup(content, 'html.parser')
                else:
                    print("  Both requests and Playwright failed")
                    print("  Tip: Set OPENTRACK_PBS environment variable with your times")
                    print("  Example: OPENTRACK_PBS='{\"200m\": \"21.18s\", \"200m SH\": \"21.83s\"}'")
                    return {}
            else:
                print("  Could not fetch OpenTrack page (due to Cloudflare)")
                print("  Install playwright for Cloudflare bypass: pip install playwright")
                print("  Alternatively, set OPENTRACK_PBS environment variable:")
                print("  Example: OPENTRACK_PBS='{\"200m\": \"21.18s\", \"200m SH\": \"21.83s\"}'")
                return {}
        else:
            soup = BeautifulSoup(response.content, 'html.parser')
        
        try:
            # Look for performance tables in the page
            tables = soup.find_all('table')
            print(f"  Found {len(tables)} tables")
            
            # Find the Performances table by looking for one with events
            perf_table = None
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) > 5:
                    # Check if second row has "Event" and "Perf" headers
                    if len(rows) > 1:
                        second_header = rows[1].get_text(strip=True)
                        if 'Event' in second_header and 'Perf' in second_header:
                            perf_table = table
                            break
            
            if not perf_table:
                print("  No performances table found")
                return {}
            
            # Extract performance data
            rows = perf_table.find_all('tr')
            for row_idx, row in enumerate(rows[2:]):  # Skip header rows (0=year, 1=headers)
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:
                    continue
                
                event_text = cells[0].get_text(strip=True)
                perf_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                
                # Check if this is an event row (event codes are just numbers or have short track/indoor indicators)
                if not perf_text or not self.parse_time(perf_text):
                    continue  # Skip non-performance rows
                
                # Parse event name
                event_key = None
                for dist in TARGET_EVENTS:
                    if event_text.strip() == dist:
                        event_key = f"{dist}m"
                        break
                
                if not event_key or not perf_text:
                    continue
                
                # Parse time (format: "21.18 (+1.3)" or "21.18")
                time_value = self.parse_time(perf_text)
                if time_value:
                    # Keep best time if we already have this event
                    if event_key in pbs:
                        try:
                            existing = float(pbs[event_key].replace('s', ''))
                            new = float(time_value.replace('s', ''))
                            if new < existing:
                                pbs[event_key] = time_value
                        except ValueError:
                            pass
                    else:
                        pbs[event_key] = time_value
                        print(f"  Found: {event_key} -> {time_value}")
            
            return pbs
            
        except Exception as e:
            print(f"  Error parsing OpenTrack response: {e}")
            return {}
    
    def scrape_world_athletics(self) -> Dict[str, str]:
        """
        Scrape personal best times from World Athletics website.
        Extracts data from JSON embedded in the page (Next.js app data).
        
        Returns:
            Dict with format: "event_variant": "time" (e.g., {"100m": "10.72s", "200m SH": "20.50s"})
        """
        print("Scraping World Athletics...")
        pbs = {}
        
        response = self._fetch_with_retry(WORLD_ATHLETICS_URL)
        if not response:
            print("  Could not fetch World Athletics page")
            return {}
        
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the script tag containing Next.js data with competitor info
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'singleCompetitor' in script.string:
                    try:
                        content = script.string
                        # Extract JSON object
                        start = content.find('{')
                        end = content.rfind('}') + 1
                        
                        if start != -1 and end > start:
                            json_str = content[start:end]
                            data = json.loads(json_str)
                            
                            # Navigate to personal bests
                            competitor = data.get('props', {}).get('pageProps', {}).get('competitor', {})
                            personal_bests = competitor.get('personalBests', {})
                            results = personal_bests.get('results', [])
                            
                            print(f"  Found {len(results)} events in personal bests")
                            
                            for result in results:
                                try:
                                    mark = result.get('mark', '')
                                    discipline = result.get('discipline', '')
                                    records = result.get('records', [])
                                    
                                    if not mark or not discipline:
                                        continue
                                    
                                    # Parse event name and detect variant
                                    event_key = self._parse_world_athletics_event(discipline)
                                    if not event_key:
                                        continue
                                    
                                    # Format time with 's' suffix
                                    time_value = mark + 's' if mark and not mark.endswith('s') else mark
                                    
                                    pbs[event_key] = time_value
                                    
                                    # Log if it's a national record
                                    if 'NR' in records:
                                        self._world_athletics_records[event_key] = True
                                        print(f"  {event_key} -> {time_value} [NR]")
                                    else:
                                        print(f"  {event_key} -> {time_value}")
                                        
                                except (ValueError, KeyError):
                                    continue
                            
                            return pbs
                            
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        print(f"  Error parsing World Athletics data: {e}")
                        continue
            
            print("  Could not find athlete data in page scripts")
            return {}
            
        except Exception as e:
            print(f"  Error scraping World Athletics: {e}")
            return {}
    
    def _parse_world_athletics_event(self, discipline: str) -> Optional[str]:
        """
        Parse World Athletics discipline name into event key format.
        
        Examples:
            "100 Metres" -> "100m"
            "200 Metres Short Track" -> "200m SH"
            "400 Metres Short Track" -> "400m SH"
            "4x100 Metres Relay" -> None (skip relays for now)
        
        Args:
            discipline: Raw discipline name from World Athletics
        
        Returns:
            Formatted event key or None if not a target event
        """
        discipline_lower = discipline.lower()
        
        # Skip relay events
        if 'relay' in discipline_lower:
            return None
        
        # Extract distance (60, 100, 200, 300, 400, 800, 1500, etc)
        for dist in TARGET_EVENTS:
            if f"{dist} metre" in discipline_lower:
                event_key = f"{dist}m"
                
                # Detect variant indicators
                if 'short track' in discipline_lower:
                    event_key += " SH"
                elif 'indoor' in discipline_lower:
                    event_key += " IN"
                
                return event_key
        
        # Check for longer distances not in TARGET_EVENTS
        match = re.search(r'(\d+)\s*(?:metre|meter)', discipline_lower)
        if match:
            dist = match.group(1)
            event_key = f"{dist}m"
            
            if 'short track' in discipline_lower:
                event_key += " SH"
            elif 'indoor' in discipline_lower:
                event_key += " IN"
            
            return event_key
        
        return None
    
    def merge_times(self, opentrack_pbs: Dict, world_pbs: Dict) -> Dict:
        """
        Merge times from multiple sources, keeping the best (fastest) for each event variant.
        
        Args:
            opentrack_pbs: Times from OpenTrack (flat dict with event variants as keys)
            world_pbs: Times from World Athletics (flat dict with event variants as keys)
        
        Returns:
            Merged dictionary with best times for each event variant
        """
        merged = {}
        
        # Process both sources
        for source_pbs in [opentrack_pbs, world_pbs]:
            for event_key, time_val in source_pbs.items():
                if event_key not in merged:
                    merged[event_key] = time_val
                else:
                    # Keep the faster time
                    try:
                        current = float(merged[event_key].replace('s', ''))
                        new = float(time_val.replace('s', ''))
                        if new < current:
                            merged[event_key] = time_val
                    except (ValueError, AttributeError):
                        pass
        
        return merged
    
    def is_national_record(self, event_key: str, time_val: str) -> bool:
        """
        Check if a time is a national record.
        
        Args:
            event_key: Event key with possible variant (e.g., "200m" or "200m SH")
            time_val: Time value (e.g., "21.18s")
        
        Returns:
            True if time matches a national record
        """
        # Extract base event name (e.g., "200m" from "200m SH")
        base_event = event_key.split()[0] if ' ' in event_key else event_key
        
        if base_event not in NATIONAL_RECORDS:
            return False
        
        try:
            record_time = float(NATIONAL_RECORDS[base_event]["time"].replace('s', ''))
            current_time = float(time_val.replace('s', ''))
            return abs(current_time - record_time) < 0.01  # Allow small rounding differences
        except (ValueError, KeyError):
            return False


def build_widget(pbs: Dict[str, str], world_athletics_records: Dict = None) -> str:
    """
    Build the README widget content with separate rows for indoor variants and NR indicators.
    
    Args:
        pbs (dict): Personal bests with event variants as keys (e.g., {"100m": "10.72s", "200m SH": "20.50s"})
        world_athletics_records (dict): Event keys that are marked as NR by World Athletics
    
    Returns:
        str: Formatted markdown table for README
    """
    if world_athletics_records is None:
        world_athletics_records = {}
    
    lines = []
    lines.append("### 🏃 Automatic Personal Best Tracker\n")
    lines.append("| Event | PB | Status |")
    lines.append("|-------|------|--------|")
    
    scraper = AthleteicsDataScraper()
    displayed_events = set()
    
    # First pass: Add events in preferred order
    for event in EVENT_ORDER:
        # Add base event
        if event in pbs and event not in displayed_events:
            time_val = pbs[event]
            # Check both confirmed records and World Athletics records
            is_nr = scraper.is_national_record(event, time_val) or (event in world_athletics_records)
            status = "🔴 NR" if is_nr else "-"
            lines.append(f"| {event} | {time_val} | {status} |")
            displayed_events.add(event)
        
        # Add any variants of this event (e.g., "200m SH", "200m IN")
        for event_key in sorted(pbs.keys()):
            if event_key.startswith(event + " ") and event_key not in displayed_events:
                time_val = pbs[event_key]
                # Check both confirmed records and World Athletics records
                is_nr = scraper.is_national_record(event_key, time_val) or (event_key in world_athletics_records)
                status = "🔴 NR" if is_nr else "-"
                lines.append(f"| {event_key} | {time_val} | {status} |")
                displayed_events.add(event_key)
    
    # Second pass: Add any remaining events not in standard order
    for event_key in sorted(pbs.keys()):
        if event_key not in displayed_events:
            time_val = pbs[event_key]
            is_nr = scraper.is_national_record(event_key, time_val) or (event_key in world_athletics_records)
            status = "🔴 NR" if is_nr else "-"
            lines.append(f"| {event_key} | {time_val} | {status} |")
            displayed_events.add(event_key)
    
    lines.append("\n> _Last updated: " + datetime.now().strftime("%d %B %Y") + "_")
    lines.append("\n> _Sourced from [OpenTrack](https://malta.opentrack.run/) & [World Athletics](https://worldathletics.org/)_")
    
    return "\n".join(lines)


def update_readme(widget_content: str, readme_path: Path = Path("README.md")):
    """
    Update the Personal Best Tracker section in README.md.
    
    Args:
        widget_content (str): New content for the PB section
        readme_path (Path): Path to README.md file
    """
    if not readme_path.exists():
        print(f"ERROR: {readme_path} not found.")
        return False
    
    content = readme_path.read_text()
    start_tag = "<!-- START_PB -->"
    end_tag = "<!-- END_PB -->"
    
    if start_tag not in content or end_tag not in content:
        print(f"ERROR: START/END tags not found in {readme_path}.")
        print(f"Please add these markers to your README.md:")
        print(f"  {start_tag}")
        print(f"  <!-- Insert Personal Best Tracker here -->")
        print(f"  {end_tag}")
        return False
    
    # Replace content between tags
    before = content.split(start_tag)[0]
    after = content.split(end_tag)[1]
    updated_content = f"{before}{start_tag}\n{widget_content}\n{end_tag}{after}"
    
    readme_path.write_text(updated_content)
    print("✓ README.md updated with new PB section.")
    return True


def main():
    """Main execution function."""
    print("=" * 60)
    print("Starting Personal Best Tracker update...")
    print("=" * 60)
    
    # Initialize scraper
    scraper = AthleteicsDataScraper()
    
    # Scrape from both sources
    opentrack_pbs = scraper.scrape_opentrack()
    world_athletics_pbs = scraper.scrape_world_athletics()
    
    # Keep track of which records came from World Athletics
    world_athletics_records = getattr(scraper, '_world_athletics_records', {})
    
    # Merge the data (taking best times from both sources)
    merged_pbs = scraper.merge_times(opentrack_pbs, world_athletics_pbs)
    
    # Always consider known valid baseline PBs (keeps fastest of scraped vs baseline)
    merged_pbs = scraper.merge_times(merged_pbs, FALLBACK_TIMES)
    
    if not merged_pbs:
        print("\nWARNING: No personal bests could be scraped from either source.")
        print("Falling back to last known times...")
        merged_pbs = FALLBACK_TIMES.copy()
    
    print(f"\nMerged {len(merged_pbs)} event variants from all sources")
    
    # Build the README widget
    widget_content = build_widget(merged_pbs, world_athletics_records)
    
    # Save widget to file (for debugging/backup)
    Path("pb_widget.md").write_text(widget_content)
    print("✓ Widget saved to pb_widget.md")
    
    # Update README.md
    success = update_readme(widget_content)
    
    if success:
        print("\n" + "=" * 60)
        print("✓ Personal Best Tracker update complete!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("✗ Failed to update README.md")
        print("=" * 60)
        exit(1)


if __name__ == "__main__":
    main()
