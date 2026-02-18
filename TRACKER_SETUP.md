# 🏃 Personal Best Tracker - Setup & Configuration

## Overview

The **Automatic Personal Best Tracker** automatically scrapes your athletics personal best times from OpenTrack and World Athletics, then updates your GitHub profile README with a beautiful markdown table. The system runs automatically every 30 days via GitHub Actions.

## Features

✅ **Automatic Scraping** - Fetches PBs from multiple sources:
- OpenTrack (local competition records)
- World Athletics (official records)

✅ **Indoor Variant Tracking** - Separate rows for indoor variants:
- Detects "SH" (short track), "IN" (indoor), or other indoor indicators automatically
- Creates separate table rows for each variant (e.g., "200m" and "200m SH")

✅ **National Record Detection** - Automatically marks national records:
- 🔴 **NR** - National Record indicator in status column

✅ **Scheduled Updates** - Runs automatically on the 18th of every month at 9:00 AM UTC

✅ **Fallback Support** - Falls back to confirmed records if scraping fails

✅ **Multi-variant Support** - Handles multiple naming conventions for indoor events

## Installation & Setup

### Prerequisites
- Python 3.8+
- Required packages: `requests`, `beautifulsoup4`

### Installation

1. **Clone or update your repository:**
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
# Or install individually:
pip install requests beautifulsoup4
```

3. **Create requirements.txt:**
```bash
cat > requirements.txt << EOF
requests>=2.31.0
beautifulsoup4>=4.12.0
EOF
```

### Configuration

#### 1. Update Your URLs

Edit `pb_updater.py` and update your athlete profile URLs:

```python
OPENTRACK_URL = "https://malta.opentrack.run/en-gb/a/YOUR_PROFILE_ID/"
WORLD_ATHLETICS_URL = "https://worldathletics.org/athletes/your-country/your-name-your-id"
```

#### 2. Configure National Records

Edit the `NATIONAL_RECORDS` dictionary in `pb_updater.py`:

```python
NATIONAL_RECORDS = {
    "200m": {"time": "21.18s", "date": "2023-04-01", "location": "Malta National Record"},
    "300m": {"time": "34.42s", "date": "2023-02-01", "location": "U20 National Record"},
    "400m": {"time": "46.83s", "date": "2023-06-01", "location": "Malta National Record"}
}
```

#### 3. Add Markers to Your README

Add these HTML comments to your README.md where you want the tracker to appear:

```markdown
<!-- START_PB -->
<!-- Personal Best Tracker will be inserted here -->
<!-- END_PB -->
```

### Indoor Variant Support

The tracker automatically detects and labels indoor event variants:

**Supported indoor indicators:**
- `SH` or `short` - Short track / indoor (creates "200m SH" row)
- `IN` or `indoor` - Indoor variant (creates "200m IN" row)
- `Indoor` - Capitalized variant (creates "200m Indoor" row)

**How it works:**
1. Script scans event names and descriptions in scraped tables
2. Detects indoor indicators (SH, IN, Indoor, short track, etc.)
3. Creates separate table rows with variant suffix
4. Outdoor events remain without suffix

**Example output:**
```
| 200m | 21.18s | 🔴 NR |
| 200m SH | 20.50s | - |
```

### GitHub Actions Setup

#### 1. Set Up GitHub Token (if using private repos)

1. Go to GitHub Settings → Personal Access Tokens → Generate new token
2. Grant `repo` permissions
3. Copy the token
4. Go to your repo → Settings → Secrets → New repository secret
5. Name it `GH_PAT` and paste the token

#### 2. Verify Workflow File

The `.github/workflows/update-pb-tracker.yml` is already configured to:
- Run on schedule (18th of every month at 9:00 AM UTC)
- Allow manual triggers via `workflow_dispatch`
- Install dependencies and run the scraper
- Commit and push updates automatically

## Usage

### Manual Trigger

Run the tracker manually anytime:

```bash
# Local testing
python pb_updater.py

# Via GitHub Actions UI
1. Go to Actions tab
2. Select "Update Personal Best Tracker"
3. Click "Run workflow"
```

### Schedule

The automation runs on:
- **When:** 18th of every month at 9:00 AM UTC
- **Frequency:** Every 30 days (approximately)

To change the schedule, edit `.github/workflows/update-pb-tracker.yml`:

```yaml
schedule:
  - cron: '0 9 18 * *'  # Change as needed (cron format)
```

## Output Format

The tracker generates a markdown table in your README with separate rows for each event and its variants:

```markdown
### 🏃 Automatic Personal Best Tracker

| Event | PB | Status |
|-------|------|--------|
| 100m | 10.72s | - |
| 200m | 21.18s | 🔴 NR |
| 200m SH | 20.50s | - |
| 300m | 34.42s | 🔴 NR |
| 400m | 46.83s | 🔴 NR |

> _Last updated: 18 February 2026_

> _Sourced from [OpenTrack](https://malta.opentrack.run/) & [World Athletics](https://worldathletics.org/)_
```

### Event Variant Labels

Indoor times appear as separate rows with variant suffixes:
- **SH** - Short Track / Indoor (e.g., "200m SH")
- **IN** - Indoor variant (e.g., "200m IN")
- **No suffix** - Outdoor/standard event

The script automatically detects and labels these variants based on page content.

## Troubleshooting

### Issue: "START/END tags not found in README.md"

**Solution:** Ensure your README.md contains:
```markdown
<!-- START_PB -->
<!-- END_PB -->
```

### Issue: Scraper returns 403 Forbidden

**Why:** Some sites may block automated requests. The script has built-in:
- Multiple retry attempts with exponential backoff
- Rotating user agents
- Random delays between requests

**Workaround:**
- The script falls back to confirmed national records
- GitHub Actions runners may have different IP reputation
- Consider manually entering times if scraping consistently fails

### Issue: No times are being found

**Debugging:**
1. Run locally: `python pb_updater.py`
2. Check the URLs in `pb_updater.py` are correct
3. Verify the websites haven't changed their HTML structure
4. Check `pb_widget.md` for actual output

### Issue: Indoor variants not being detected

**If indoor times aren't appearing as separate rows:**

1. Check the actual pages to see how indoor is labeled (SH, IN, Indoor, etc.)
2. Verify the HTML structure contains these labels
3. Add the label to the detection logic if needed:

```python
# In scrape_opentrack() or scrape_world_athletics()
if 'your_label' in text.lower():
    variant = "YOUR_LABEL"
```

4. Test locally: `python pb_updater.py`

### Issue: Indoor variants not marked as national records

Indoor variants (e.g., "200m SH") check against the base event's national record. Currently:
- "200m SH" checks against "200m" national record
- To create separate indoor-specific records, update `NATIONAL_RECORDS`:

```python
NATIONAL_RECORDS = {
    "200m": {"time": "21.18s", "date": "2023-04-01", "location": "Outdoor NR"},
    "200m_SH": {"time": "20.50s", "date": "2024-01-15", "location": "Indoor NR"},
}
```

Then update `is_national_record()` to handle underscore variants if needed.

## Advanced Configuration

### Custom Events

Edit `TARGET_EVENTS` to add or remove events:

```python
TARGET_EVENTS = ["60", "100", "200", "300", "400", "800", "1500", "5000"]
```

### Custom Event Display Order

Edit `EVENT_ORDER` to control the display sequence:

```python
EVENT_ORDER = ["100m", "200m", "400m", "800m", "1500m", "5000m"]
```

**Note:** Indoor variants automatically follow their base event. For example, if "200m" is listed, any "200m SH" or "200m IN" variants will appear immediately after it.

### Custom Indoor Variant Indicators

To add support for more indoor variant labels, edit the scraper methods. For example, in `scrape_opentrack()`:

```python
# Detect indoor variant indicators
if 'sh' in text.lower() or 'short' in text.lower():
    variant = "SH"
elif 'in' in text.lower() or 'indoor' in text.lower():
    variant = "IN"
elif 'track' in text.lower():  # Add custom indicator
    variant = "TR"
```

### Adding More Data Sources

To add scraping from additional sources, create a new method:

```python
def scrape_custom_source(self) -> Dict[str, str]:
    """Scrape from your custom source."""
    pbs = {}
    response = self._fetch_with_retry("https://example.com/athlete")
    if response:
        soup = BeautifulSoup(response.content, 'html.parser')
        # Parse and extract times with variants
        # Return format: {"100m": "10.72s", "200m SH": "20.50s"}
    return pbs
```

Then update the `main()` function to merge the new source.

## Maintenance

### Regular Updates

- **Monthly:** The tracker auto-updates on the 18th
- **Manual:** Run `python pb_updater.py` anytime to update
- **Manual (GitHub):** Trigger via Actions tab

### Backup

The script maintains:
- `pb_widget.md` - Latest widget output (for debugging/backup)
- Git history - All updates are committed with timestamps

## Cron Schedule Reference

The workflow runs on cron format: `minute hour day month dayofweek`

Current: `0 9 18 * *` (9:00 AM UTC on the 18th of every month)

**Common alternatives:**
- `0 9 1 * *` - 1st of every month
- `0 9 15 * *` - 15th of every month
- `0 0 * * 0` - Every Sunday at midnight UTC
- `0 9 * * 0` - Every Sunday at 9 AM UTC

## File Structure

```
your-repo/
├── pb_updater.py                    # Main scraper script
├── pb_widget.md                     # Latest tracker widget output
├── requirements.txt                 # Python dependencies
├── TRACKER_SETUP.md                 # This file
├── README.md                        # Your profile README
└── .github/
    └── workflows/
        └── update-pb-tracker.yml    # GitHub Actions workflow
```

## Contributing

To improve the tracker:

1. Test changes locally: `python pb_updater.py`
2. Update the script in `pb_updater.py`
3. Commit with clear messages
4. Push and verify GitHub Actions runs successfully

## Support & Debugging

### Enable Verbose Output

The script has built-in logging. For more details:
1. Add `print()` statements to `pb_updater.py`
2. Check GitHub Actions logs: Actions tab → Workflow run → View logs

### Common Cron Issues

- Ensure timezone is UTC for cron schedules
- GitHub Actions runs on UTC regardless of repo settings
- Test cron expressions at [crontab.guru](https://crontab.guru)

## License

This automation is part of your GitHub profile repository.

---

**Questions?** Check the logs in GitHub Actions or run locally to debug!
