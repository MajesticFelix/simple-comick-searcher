#!/usr/bin/env python3
"""
Comic Search Script using Comick.io API

This script allows you to search for comics by name using the Comick.io API.
Features intelligent caching, robust error handling, and improved HTTP headers.

Usage:
    python comic_search.py "comic name"
    python comic_search.py --help

Examples:
    python comic_search.py "One Piece"
    python comic_search.py "Attack on Titan"
    python comic_search.py "Naruto" --limit 5
    python comic_search.py --clear-cache  # Clear all cached data
"""

import argparse
import hashlib
import json
import os
import platform
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class CacheManager:
    """Manages local caching of API responses"""
    
    def __init__(self, cache_dir: str = ".comic_cache", cache_duration_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_duration = timedelta(hours=cache_duration_hours)
        
        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(exist_ok=True)
        
        # Create a .gitignore file to prevent caching from being committed
        gitignore_path = self.cache_dir / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text("*\n!.gitignore\n")
    
    def _get_cache_key(self, url: str, params: Dict) -> str:
        """Generate a unique cache key for the request"""
        # Create a unique key based on URL and parameters
        cache_string = f"{url}_{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key"""
        return self.cache_dir / f"{cache_key}.json"
    
    def get(self, url: str, params: Dict) -> Optional[Dict]:
        """Get cached response if available and not expired"""
        cache_key = self._get_cache_key(url, params)
        cache_path = self._get_cache_path(cache_key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # Check if cache has expired
            cached_time = datetime.fromisoformat(cached_data['timestamp'])
            if datetime.now() - cached_time > self.cache_duration:
                # Cache expired, remove file
                cache_path.unlink()
                return None
            
            print(f"📱 Using cached result (saved {datetime.now() - cached_time} ago)")
            return cached_data['response']
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Corrupted cache file, remove it
            try:
                cache_path.unlink()
            except OSError:
                pass
            return None
    
    def set(self, url: str, params: Dict, response: Dict):
        """Store response in cache"""
        cache_key = self._get_cache_key(url, params)
        cache_path = self._get_cache_path(cache_key)
        
        cached_data = {
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'params': params,
            'response': response
        }
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"⚠️  Warning: Could not save to cache: {e}")
    
    def clear(self):
        """Clear all cached data"""
        deleted_count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                deleted_count += 1
            except OSError:
                pass
        
        print(f"🗑️  Cleared {deleted_count} cached files")
        return deleted_count
    
    def get_cache_info(self):
        """Get information about cached data"""
        cache_files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files if f.exists())
        
        return {
            'count': len(cache_files),
            'size_mb': total_size / (1024 * 1024),
            'location': str(self.cache_dir.absolute())
        }


class EnhancedComickAPI:
    """Enhanced wrapper for the Comick.io API with robust HTTP handling"""
    
    BASE_URL = "https://comick-api-proxy.notaspider.dev/api"
    APP_VERSION = "1.2.0"
    CONTACT_EMAIL = "comic-search@example.com"  # Replace with your actual contact
    
    def __init__(self, show_rate_limit_info: bool = True, use_cache: bool = True):
        self.show_rate_limit_info = show_rate_limit_info
        self.cache = CacheManager() if use_cache else None
        self.last_request_time = 0
        self.min_request_interval = 0.1  # Minimum 100ms between requests
        
        # Create session with enhanced configuration
        self.session = self._create_enhanced_session()
    
    def _create_enhanced_session(self) -> requests.Session:
        """Create a session with browser-like headers and retry strategy"""
        session = requests.Session()
        
        # Get system information
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        os_info = self._get_os_info()
        
        # Create descriptive and stable User-Agent (following the working pattern)
        user_agent = (
            f"ComicReader/{self.APP_VERSION} "
            f"(+https://github.com/user/comic-reader) "
            f"Python-requests/{requests.__version__}"
        )
        
        # Set minimal headers that work (keep it simple and similar to working version)
        session.headers.update({
            'User-Agent': user_agent,
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        # Configure retry strategy for robustness
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,  # Wait 1, 2, 4 seconds between retries
            respect_retry_after_header=True
        )
        
        # Mount adapter with retry strategy
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _get_os_info(self) -> str:
        """Get OS information for User-Agent"""
        system = platform.system()
        release = platform.release()
        
        # Format OS info similar to browser User-Agents
        if system == "Darwin":
            # macOS
            mac_version = platform.mac_ver()[0]
            return f"Macintosh; Intel Mac OS X {mac_version.replace('.', '_')}"
        elif system == "Windows":
            return f"Windows NT {release}"
        elif system == "Linux":
            return f"X11; Linux {platform.machine()}"
        else:
            return f"{system} {release}"
    
    def _pace_request(self):
        """Implement request pacing to be respectful to the API"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _handle_rate_limit_with_backoff(self, response: requests.Response, attempt: int = 1) -> bool:
        """Handle rate limiting with exponential backoff"""
        if response.status_code != 429:
            return False
        
        # Get retry-after header or calculate backoff
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            try:
                wait_time = int(retry_after)
            except ValueError:
                wait_time = 60  # Default to 60 seconds
        else:
            # Exponential backoff: 2^attempt + random jitter
            wait_time = (2 ** attempt) + random.uniform(0, 1)
        
        print(f"⚠️  Rate limit exceeded (attempt {attempt}). Waiting {wait_time:.1f} seconds...")
        time.sleep(wait_time)
        return True
    
    def _make_request(self, url: str, params: Dict, max_retries: int = 3) -> Optional[requests.Response]:
        """Make a request with pacing and backoff handling"""
        for attempt in range(1, max_retries + 1):
            self._pace_request()
            
            try:
                response = self.session.get(url, params=params, timeout=15)
                
                # Handle rate limiting with backoff
                if response.status_code == 429:
                    if attempt < max_retries and self._handle_rate_limit_with_backoff(response, attempt):
                        continue
                    else:
                        print(f"❌ Rate limit exceeded after {max_retries} attempts")
                        return None
                
                # Check for other HTTP errors
                response.raise_for_status()
                return response
                
            except requests.exceptions.Timeout:
                print(f"⏱️  Request timeout (attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)  # Exponential backoff for timeouts
                    continue
                
            except requests.exceptions.RequestException as e:
                print(f"🔗 Network error (attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
        
        return None
    
    def search_comics(self, query: str, limit: int = 15, page: int = 1) -> List[Dict]:
        """
        Search for comics by name/title
        
        Args:
            query: The comic name to search for
            limit: Maximum number of results (default: 15, max: 300)
            page: Page number for pagination (default: 1, max: 50)
            
        Returns:
            List of comic dictionaries containing comic information
        """
        url = f"{self.BASE_URL}/v1.0/search/"
        
        params = {
            'q': query,
            'limit': min(limit, 300),  # API max is 300
            'page': min(page, 50),     # API max is 50
            'type': 'comic'
        }
        
        # Check cache first
        if self.cache:
            cached_result = self.cache.get(url, params)
            if cached_result is not None:
                return cached_result
        
        print("🌐 Fetching from API...")
        response = self._make_request(url, params)
        
        if response is None:
            return []
        
        # Display rate limit info if available and enabled
        if self.show_rate_limit_info and 'x-ratelimit-remaining' in response.headers:
            remaining = response.headers.get('x-ratelimit-remaining')
            limit_header = response.headers.get('x-ratelimit-limit')
            reset = response.headers.get('x-ratelimit-reset')
            print(f"ℹ️  Rate limit: {remaining}/{limit_header} requests remaining (resets in {reset}s)")
        
        try:
            result = response.json()
            
            # Cache the result
            if self.cache:
                self.cache.set(url, params, result)
            
            return result
            
        except json.JSONDecodeError:
            print("❌ Invalid JSON response from API")
            return []
    
    def get_comic_details(self, slug: str) -> Optional[Dict]:
        """
        Get detailed information about a specific comic
        
        Args:
            slug: The comic's slug identifier
            
        Returns:
            Dictionary containing detailed comic information
        """
        url = f"{self.BASE_URL}/comic/{slug}/"
        params = {}  # No params for this endpoint
        
        # Check cache first
        if self.cache:
            cached_result = self.cache.get(url, params)
            if cached_result is not None:
                return cached_result
        
        print("🌐 Fetching comic details from API...")
        response = self._make_request(url, params)
        
        if response is None:
            return None
        
        try:
            result = response.json()
            
            # Cache the result
            if self.cache:
                self.cache.set(url, params, result)
            
            return result
            
        except json.JSONDecodeError:
            print("❌ Invalid JSON response from API")
            return None


def build_cover_url(comic: Dict) -> Optional[str]:
    """Build cover image URL from comic data"""
    if not comic or not isinstance(comic, dict):
        return None
    
    md_covers = comic.get('md_covers')
    if md_covers and isinstance(md_covers, list) and len(md_covers) > 0:
        first_cover = md_covers[0]
        if first_cover and isinstance(first_cover, dict):
            b2key = first_cover.get('b2key')
            if b2key and isinstance(b2key, str):
                return f"https://meo.comick.pictures/{b2key}"
    return None


def save_results_to_file(results: List[Dict], detailed_results: List[Optional[Dict]], filename: str, detailed_mode: bool):
    """Save search results to a file in various formats"""
    import csv
    from pathlib import Path
    
    # Create "saved" directory if it doesn't exist
    saved_dir = Path("saved")
    saved_dir.mkdir(exist_ok=True)
    
    # Combine the saved directory with the filename
    file_path = saved_dir / filename
    file_ext = file_path.suffix.lower()
    
    try:
        if file_ext == '.json':
            # Save as JSON
            data_to_save = []
            for i, comic in enumerate(results):
                if detailed_mode and detailed_results[i]:
                    # Combine search result with detailed data
                    combined_data = {
                        'search_result': comic,
                        'detailed_data': detailed_results[i]
                    }
                    data_to_save.append(combined_data)
                else:
                    data_to_save.append(comic)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
                
        elif file_ext == '.csv':
            # Save as CSV - flatten the data
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write headers
                headers = ['title', 'slug', 'year', 'status', 'country', 'rating', 'followers', 'genres']
                if detailed_mode:
                    headers.extend(['authors', 'artists', 'publishers', 'themes', 'content_rating', 'demographic', 'rank', 'latest_chapter', 'cover_url'])
                writer.writerow(headers)
                
                # Write data
                for i, comic in enumerate(results):
                    detailed = detailed_results[i] if detailed_mode else None
                    row = extract_csv_row(comic, detailed, detailed_mode)
                    writer.writerow(row)
                    
        else:
            # Save as plain text (default for .txt or any other extension)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"Comic Search Results\n")
                f.write(f"={'=' * 50}\n\n")
                
                for i, comic in enumerate(results, 1):
                    detailed = detailed_results[i-1] if detailed_mode else None
                    f.write(f"Result {i}\n")
                    f.write(f"{'-' * 20}\n")
                    f.write(format_comic_info(comic, detailed_mode, detailed))
                    f.write(f"\n\n")
        
        print(f"📁 Results saved to: {file_path.absolute()}")
        
    except Exception as e:
        print(f"❌ Error saving to file: {e}")


def extract_csv_row(comic: Dict, detailed_data: Optional[Dict], detailed_mode: bool) -> List[str]:
    """Extract data for CSV row"""
    # Use detailed data if available for basic fields
    if detailed_data and 'comic' in detailed_data:
        data = detailed_data['comic']
    else:
        data = comic
    
    # Basic fields
    title = data.get('title', '')
    slug = data.get('slug', '')
    year = str(data.get('year', ''))
    
    # Status
    status_map = {1: "Ongoing", 2: "Completed", 3: "Cancelled", 4: "Hiatus"}
    status = status_map.get(data.get('status'), '')
    
    country = data.get('country', '').upper()
    
    # Rating
    rating_value = data.get('bayesian_rating') or data.get('rating')
    rating = str(rating_value) if rating_value else ''
    
    # Followers
    followers = data.get('user_follow_count') or data.get('follow_count')
    followers_str = str(followers) if followers else ''
    
    # Genres
    genres = []
    if comic.get('md_comic_md_genres'):
        for genre in comic.get('md_comic_md_genres', []):
            if genre and genre.get('md_genres', {}).get('name'):
                genres.append(genre['md_genres']['name'])
    elif detailed_data and detailed_data.get('comic', {}).get('md_comic_md_genres'):
        for genre in detailed_data['comic'].get('md_comic_md_genres', []):
            if genre and genre.get('md_genres', {}).get('name'):
                genres.append(genre['md_genres']['name'])
    
    genres_str = '; '.join(genres)
    
    row = [title, slug, year, status, country, rating, followers_str, genres_str]
    
    # Add detailed fields if in detailed mode
    if detailed_mode and detailed_data:
        # Authors
        authors = []
        for author in detailed_data.get('authors', []):
            if author and author.get('name'):
                authors.append(author['name'])
        authors_str = '; '.join(authors)
        
        # Artists
        artists = []
        for artist in detailed_data.get('artists', []):
            if artist and artist.get('name'):
                artists.append(artist['name'])
        artists_str = '; '.join(artists)
        
        # Publishers
        publishers = []
        comic_data = detailed_data.get('comic', {})
        mu_comics = comic_data.get('mu_comics')
        if mu_comics and isinstance(mu_comics, dict):
            for publisher in mu_comics.get('mu_comic_publishers', []):
                if publisher and publisher.get('mu_publishers', {}).get('title'):
                    publishers.append(publisher['mu_publishers']['title'])
        publishers_str = '; '.join(publishers)
        
        # Themes
        themes = []
        if comic_data:
            # From genres
            for genre in comic_data.get('md_comic_md_genres', []):
                if genre and genre.get('md_genres', {}).get('group') == 'Theme':
                    themes.append(genre['md_genres']['name'])
            # From categories
            if mu_comics:
                for theme in mu_comics.get('mu_comic_categories', []):
                    if theme and theme.get('mu_categories', {}).get('title'):
                        themes.append(theme['mu_categories']['title'])
        themes_str = '; '.join(themes)
        
        content_rating = data.get('content_rating', '')
        
        # Demographic
        demographic_map = {1: "Shounen", 2: "Shoujo", 3: "Seinen", 4: "Josei", 5: "None"}
        demographic = demographic_map.get(data.get('demographic'), '')
        
        rank = str(data.get('follow_rank', ''))
        latest_chapter = str(data.get('last_chapter', ''))
        
        # Cover URL
        cover_url = ''
        if comic.get('md_covers'):
            cover_url = build_cover_url(comic) or ''
        elif detailed_data.get('comic', {}).get('md_covers'):
            cover_url = build_cover_url(detailed_data['comic']) or ''
        
        row.extend([authors_str, artists_str, publishers_str, themes_str, content_rating, demographic, rank, latest_chapter, cover_url])
    
    return row


def format_comic_info(comic: Dict, show_detailed: bool = False, detailed_data: Optional[Dict] = None) -> str:
    """Format comic information for display"""
    # When we have detailed data, extract the comic info from the nested structure
    if detailed_data and 'comic' in detailed_data:
        data = detailed_data['comic']
    else:
        data = comic
    
    title = data.get('title', 'Unknown Title')
    slug = data.get('slug', '')
    
    # Get alternative titles from search results (they have md_titles) or detailed data
    alt_titles = []
    # For search results
    md_titles = comic.get('md_titles')
    if md_titles and isinstance(md_titles, list):
        for alt in md_titles:
            if alt and isinstance(alt, dict) and alt.get('title') and alt['title'] != title:
                alt_titles.append(alt['title'])
    # For detailed data, check if it has md_titles at comic level
    elif data and data.get('md_titles'):
        md_titles_detailed = data.get('md_titles')
        if md_titles_detailed and isinstance(md_titles_detailed, list):
            for alt in md_titles_detailed:
                if alt and isinstance(alt, dict) and alt.get('title') and alt['title'] != title:
                    alt_titles.append(alt['title'])
    
    # Basic info (always shown)
    info_lines = [
        f"📚 Title: {title}",
        f"🔗 Slug: {slug}"
    ]
    
    if alt_titles:
        max_alt = 3 if not show_detailed else len(alt_titles)
        info_lines.append(f"📝 Alt Titles: {', '.join(alt_titles[:max_alt])}")
    
    # Description - full if detailed, truncated if not
    if data.get('desc'):
        if show_detailed:
            info_lines.append(f"📖 Description: {data['desc']}")
        else:
            desc = data['desc'][:200] + "..." if len(data.get('desc', '')) > 200 else data.get('desc', '')
            info_lines.append(f"📖 Description: {desc}")
    
    # Basic details (always shown)
    if data.get('year'):
        info_lines.append(f"📅 Year: {data['year']}")
    
    if data.get('status'):
        status_map = {1: "Ongoing", 2: "Completed", 3: "Cancelled", 4: "Hiatus"}
        status_text = status_map.get(data['status'], f"Status {data['status']}")
        info_lines.append(f"📊 Status: {status_text}")
    
    if data.get('country'):
        info_lines.append(f"🌍 Country: {data['country'].upper()}")
    
    # Rating - try bayesian_rating first, then rating
    rating_value = data.get('bayesian_rating') or data.get('rating')
    if rating_value:
        try:
            rating = float(rating_value)
            info_lines.append(f"⭐ Rating: {rating:.1f}/10")
        except (ValueError, TypeError):
            info_lines.append(f"⭐ Rating: {rating_value}/10")
    
    # Followers - use the right field name
    followers = data.get('user_follow_count') or data.get('follow_count')
    if followers:
        info_lines.append(f"👥 Followers: {followers:,}")
    
    # Genre information - handle both search and detailed data structures
    genres = []
    # For search results
    comic_genres = comic.get('md_comic_md_genres')
    if comic_genres and isinstance(comic_genres, list):
        for genre in comic_genres:
            if genre and isinstance(genre, dict):
                md_genres = genre.get('md_genres')
                if md_genres and isinstance(md_genres, dict) and md_genres.get('name'):
                    genres.append(md_genres['name'])
    # For detailed data, check if it has md_comic_md_genres under comic
    elif detailed_data and detailed_data.get('comic'):
        detailed_comic = detailed_data.get('comic', {})
        detailed_genres = detailed_comic.get('md_comic_md_genres')
        if detailed_genres and isinstance(detailed_genres, list):
            for genre in detailed_genres:
                if genre and isinstance(genre, dict):
                    md_genres = genre.get('md_genres')
                    if md_genres and isinstance(md_genres, dict) and md_genres.get('name'):
                        genres.append(md_genres['name'])
    
    if genres:
        max_genres = 5 if not show_detailed else len(genres)
        info_lines.append(f"🏷️  Genres: {', '.join(genres[:max_genres])}")
    
    # Additional detailed information (only when --detailed is used)
    if show_detailed and detailed_data:
        
        # Authors
        authors = []
        author_list = detailed_data.get('authors')
        if author_list and isinstance(author_list, list):
            for author in author_list:
                if author and isinstance(author, dict) and author.get('name'):
                    authors.append(author['name'])
        if authors:
            info_lines.append(f"✍️  Authors: {', '.join(authors)}")
        
        # Artists
        artists = []
        artist_list = detailed_data.get('artists')
        if artist_list and isinstance(artist_list, list):
            for artist in artist_list:
                if artist and isinstance(artist, dict) and artist.get('name'):
                    artists.append(artist['name'])
        if artists:
            info_lines.append(f"🎨 Artists: {', '.join(artists)}")
        
        # Publishers - correct path based on JSON structure
        publishers = []
        comic_data = detailed_data.get('comic')
        if comic_data and isinstance(comic_data, dict):
            mu_comics = comic_data.get('mu_comics')
            if mu_comics and isinstance(mu_comics, dict):
                publisher_list = mu_comics.get('mu_comic_publishers')
                if publisher_list and isinstance(publisher_list, list):
                    for publisher in publisher_list:
                        if publisher and isinstance(publisher, dict):
                            mu_publishers = publisher.get('mu_publishers')
                            if mu_publishers and isinstance(mu_publishers, dict) and mu_publishers.get('title'):
                                publishers.append(mu_publishers['title'])
        if publishers:
            info_lines.append(f"🏢 Publishers: {', '.join(publishers)}")
        
        # Themes - extract from genres with group="Theme" or from mu_comic_categories
        themes = []
        # Get themes from genres
        if comic_data and isinstance(comic_data, dict):
            theme_genres = comic_data.get('md_comic_md_genres')
            if theme_genres and isinstance(theme_genres, list):
                for genre in theme_genres:
                    if genre and isinstance(genre, dict):
                        md_genres = genre.get('md_genres')
                        if md_genres and isinstance(md_genres, dict) and md_genres.get('group') == 'Theme' and md_genres.get('name'):
                            themes.append(md_genres['name'])
            # Also check mu_comic_categories
            mu_comics = comic_data.get('mu_comics')
            if mu_comics and isinstance(mu_comics, dict):
                category_list = mu_comics.get('mu_comic_categories')
                if category_list and isinstance(category_list, list):
                    for theme in category_list:
                        if theme and isinstance(theme, dict):
                            mu_categories = theme.get('mu_categories')
                            if mu_categories and isinstance(mu_categories, dict) and mu_categories.get('title'):
                                themes.append(mu_categories['title'])
        if themes:
            info_lines.append(f"🎭 Themes: {', '.join(themes)}")
        
        # Content Rating
        if data.get('content_rating'):
            info_lines.append(f"📋 Content Rating: {data['content_rating']}")
        
        # Demographic
        if data.get('demographic'):
            demographic_map = {1: "Shounen", 2: "Shoujo", 3: "Seinen", 4: "Josei", 5: "None"}
            demographic_text = demographic_map.get(data['demographic'], f"Demographic {data['demographic']}")
            info_lines.append(f"👥 Demographic: {demographic_text}")
        
        # Rank
        if data.get('follow_rank'):
            info_lines.append(f"🏆 Rank: #{data['follow_rank']}")
        
        # Latest chapter
        if data.get('last_chapter'):
            info_lines.append(f"📖 Latest Chapter: {data['last_chapter']}")
        
        # Cover image - check both search and detailed data for covers
        cover_url = None
        comic_covers = comic.get('md_covers')
        if comic_covers and isinstance(comic_covers, list):
            cover_url = build_cover_url(comic)
        else:
            detailed_comic = detailed_data.get('comic')
            if detailed_comic and isinstance(detailed_comic, dict):
                detailed_covers = detailed_comic.get('md_covers')
                if detailed_covers and isinstance(detailed_covers, list):
                    cover_url = build_cover_url(detailed_comic)
            
        if cover_url:
            info_lines.append(f"🖼️  Cover Image: {cover_url}")
    
    return "\n".join(info_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Enhanced comic search using Comick.io API with intelligent caching and robust HTTP handling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "One Piece"                 # Search for One Piece
  %(prog)s "Attack on Titan" --limit 5 # Search with custom limit
  %(prog)s "Naruto" --detailed         # Show detailed information
  %(prog)s "One Piece" --save-to results.json    # Save results to saved/results.json
  %(prog)s "One Piece" --detailed --save-to detailed.csv # Save detailed results to saved/detailed.csv
  %(prog)s --cache-info                # Show cache information
  %(prog)s --clear-cache               # Clear all cached data
        """
    )
    
    parser.add_argument('query', nargs='?', help='Comic name to search for')
    parser.add_argument('--limit', '-l', type=int, default=10,
                       help='Maximum number of results to show (default: 10, max: 300)')
    parser.add_argument('--page', '-p', type=int, default=1,
                       help='Page number for pagination (default: 1, max: 50)')
    parser.add_argument('--detailed', '-d', action='store_true',
                       help='Show detailed information for each comic')
    parser.add_argument('--json', '-j', action='store_true',
                       help='Output raw JSON response')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Suppress rate limit information')
    parser.add_argument('--no-cache', action='store_true',
                       help='Disable caching for this request')
    parser.add_argument('--clear-cache', action='store_true',
                       help='Clear all cached data and exit')
    parser.add_argument('--cache-info', action='store_true',
                       help='Show cache information and exit')
    parser.add_argument('--debug', action='store_true',
                       help='Show debug information including headers')
    parser.add_argument('--save-to', metavar='FILE', type=str,
                       help='Save all search results to saved/FILE (supports .json, .txt, .csv formats)')
    
    args = parser.parse_args()
    
    # Handle cache management commands
    if args.clear_cache:
        cache = CacheManager()
        cache.clear()
        return
    
    if args.cache_info:
        cache = CacheManager()
        info = cache.get_cache_info()
        print(f"📊 Cache Information:")
        print(f"   Files: {info['count']}")
        print(f"   Size: {info['size_mb']:.2f} MB")
        print(f"   Location: {info['location']}")
        return
    
    # Validate arguments
    if not args.query:
        parser.print_help()
        print("\nError: Query is required (unless using --clear-cache or --cache-info)")
        sys.exit(1)
    
    if args.limit < 1 or args.limit > 300:
        print("Error: Limit must be between 1 and 300")
        sys.exit(1)
    
    if args.page < 1 or args.page > 50:
        print("Error: Page must be between 1 and 50")
        sys.exit(1)
    
    if not args.query.strip():
        print("Error: Query cannot be empty")
        sys.exit(1)
    
    # Search for comics
    api = EnhancedComickAPI(
        show_rate_limit_info=not args.quiet,
        use_cache=not args.no_cache
    )
    
    # Show debug info if requested
    if args.debug:
        print(f"🔧 Debug Info:")
        print(f"   User-Agent: {api.session.headers.get('User-Agent')}")
        print(f"   Cache enabled: {api.cache is not None}")
        print()
    
    print(f"🔍 Searching for '{args.query}'...")
    
    results = api.search_comics(args.query, args.limit, args.page)
    
    if not results:
        print("❌ No comics found or error occurred")
        sys.exit(1)
    
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return
    
    print(f"\n✅ Found {len(results)} comic(s):\n")
    
    # Collect detailed results if needed (for saving or display)
    detailed_results = []
    
    for i, comic in enumerate(results, 1):
        print(f"━━━ Result {i} ━━━")
        
        # If detailed view is requested, fetch full comic details
        detailed_data = None
        if args.detailed and comic.get('slug'):
            detailed_data = api.get_comic_details(comic['slug'])
        
        detailed_results.append(detailed_data)
        
        print(format_comic_info(comic, args.detailed, detailed_data))
        print()
    
    # Save to file if requested
    if args.save_to:
        save_results_to_file(results, detailed_results, args.save_to, args.detailed)


if __name__ == "__main__":
    main()