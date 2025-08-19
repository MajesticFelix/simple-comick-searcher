# Comic Search Tool

A simple Python-based command-line tool for searching comics using the Comick.io API. Features intelligent caching, robust error handling, and multiple export formats.

## ✨ Features

- 🔍 **Fast Comic Search**: Search thousands of comics by title with pagination support
- 📱 **Smart Caching**: Automatic 24-hour caching to reduce API calls and improve performance
- 🔄 **Robust HTTP Handling**: Built-in retry logic, rate limiting, and Cloudflare compatibility
- 📊 **Multiple Export Formats**: Save results as JSON, CSV, or formatted text
- 🎯 **Detailed Information**: Optional detailed mode with authors, publishers, themes, and more
- 🛠️ **Debug Tools**: Cache management and debug modes for troubleshooting

## 🚀 Quick Start

### Installation

1. **Clone or download** this repository
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Basic Usage

Search for a comic:
```bash
python comic_search.py "One Piece"
```

That's it! The script will search for "One Piece" and display the results with cover images, ratings, and basic information.

## 📖 Usage Examples

### Simple Searches
```bash
# Basic search
python comic_search.py "Attack on Titan"

# Limit results
python comic_search.py "Naruto" --limit 5

# Search with pagination
python comic_search.py "Dragon Ball" --page 2
```

### Detailed Information
```bash
# Get detailed information (authors, publishers, themes, etc.)
python comic_search.py "One Piece" --detailed

# Show only 3 detailed results
python comic_search.py "Demon Slayer" --detailed --limit 3
```

### Export Results
```bash
# Save as JSON
python comic_search.py "One Piece" --save-to results.json

# Save as CSV (great for spreadsheets)
python comic_search.py "One Piece" --save-to results.csv

# Save detailed data as CSV
python comic_search.py "One Piece" --detailed --save-to detailed.csv

# Save as formatted text
python comic_search.py "One Piece" --save-to results.txt
```

### Cache Management
```bash
# Check cache status
python comic_search.py --cache-info

# Clear cache
python comic_search.py --clear-cache

# Bypass cache for fresh results
python comic_search.py "One Piece" --no-cache
```

### Advanced Options
```bash
# JSON output for scripting
python comic_search.py "One Piece" --json

# Debug mode (shows HTTP headers and cache info)
python comic_search.py "One Piece" --debug

# Quiet mode (suppress rate limit info)
python comic_search.py "One Piece" --quiet
```

## 📋 Command-Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--limit LIMIT` | `-l` | Maximum results to show (default: 10, max: 300) |
| `--page PAGE` | `-p` | Page number for pagination (default: 1, max: 50) |
| `--detailed` | `-d` | Show detailed information for each comic |
| `--json` | `-j` | Output raw JSON response |
| `--quiet` | `-q` | Suppress rate limit information |
| `--no-cache` | | Disable caching for this request |
| `--clear-cache` | | Clear all cached data and exit |
| `--cache-info` | | Show cache information and exit |
| `--debug` | | Show debug information including headers |
| `--save-to FILE` | | Save results to saved/FILE (supports .json, .txt, .csv) |

## 📊 Output Formats

### Console Output
By default, results are displayed in a formatted, human-readable format:

```
✅ Found 10 comic(s):

━━━ Result 1 ━━━
📚 Title: One Piece
🔗 Slug: one-piece
📅 Year: 1997
📊 Status: Ongoing
🌍 Country: JP
⭐ Rating: 9.2/10
👥 Followers: 125,432
🏷️  Genres: Action, Adventure, Comedy, Drama, Shounen
```

### Export Formats

#### JSON Export
Complete data structure with all available fields:
```json
[
  {
    "title": "One Piece",
    "slug": "one-piece",
    "year": 1997,
    "status": 1,
    "rating": 9.2,
    "md_comic_md_genres": [...]
  }
]
```

#### CSV Export
Tabular format perfect for spreadsheets:
```csv
title,slug,year,status,country,rating,followers,genres
One Piece,one-piece,1997,Ongoing,JP,9.2,125432,"Action; Adventure; Comedy"
```

#### Text Export
Formatted text similar to console output, saved to file.

## 🗂️ File Structure

After running the script, you'll see these directories:

```
comic-search/
├── comic_search.py          # Main script
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── .comic_cache/           # Cached API responses (auto-created)
│   ├── .gitignore         # Prevents cache from being committed
│   └── *.json             # Cached search results
└── saved/                  # Exported results (auto-created)
    ├── results.json
    ├── results.csv
    └── results.txt
```

## 💡 Tips & Best Practices

### Performance Tips
- **Use caching**: Results are cached for 24 hours by default. Use `--cache-info` to check cache status.
- **Reasonable limits**: Start with `--limit 10` and increase as needed. Maximum is 300.
- **Batch exports**: Use `--save-to` to export large result sets for offline analysis.

### Search Tips
- **Exact titles work best**: "One Piece" will find the main series quickly.
- **Try variations**: If you don't find what you're looking for, try alternative spellings or shorter names.
- **Use pagination**: Popular search terms may have many results. Use `--page 2`, `--page 3`, etc.

### Export Tips
- **CSV for analysis**: Use CSV format if you want to analyze data in Excel or Google Sheets.
- **JSON for scripting**: Use JSON format if you're building other tools on top of this data.
- **Detailed mode**: Add `--detailed` when exporting to get comprehensive information including authors, publishers, and themes.

## 🔧 Troubleshooting

### Common Issues

**"No comics found"**
- Check your spelling and try shorter or alternative titles
- Some comics might be listed under different names
- Try searching without quotes or special characters

**Rate limiting messages**
- The script handles this automatically with exponential backoff
- Wait times are displayed and respected automatically
- Consider using cached results with `--cache-info`

**Network timeouts**
- The script retries automatically up to 3 times
- Check your internet connection
- Try again later if the API is experiencing issues

**Cache issues**
- Use `--clear-cache` to reset all cached data
- Use `--no-cache` to bypass cache for a single search
- Check `--cache-info` to see cache status

### Debug Mode
Use `--debug` to see detailed information about requests:
```bash
python comic_search.py "One Piece" --debug
```

This shows:
- User-Agent string being used
- Cache status
- HTTP request details
- Rate limiting information

## 📡 API Information

This tool uses the Comick.io API:
- **Rate Limit**: 200 requests per minute per IP
- **Base URL**: `https://api.comick.fun`
- **Response Format**: JSON
- **Cache Duration**: 24 hours (configurable)

The script automatically handles rate limiting, retries, and Cloudflare protection.

## 🛡️ Privacy & Ethics

- **Respectful usage**: Built-in rate limiting and request pacing
- **No data collection**: All data comes directly from Comick.io API
- **Local caching**: Cache is stored locally and not shared
- **No tracking**: The tool doesn't track or log user behavior

## 📄 License

This project is for educational and personal use. Please respect the Comick.io API terms of service and rate limits.

---

**Need help?** Run `python comic_search.py --help` for quick reference, or check the troubleshooting section above.