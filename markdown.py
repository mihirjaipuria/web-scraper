# markdown.py

import asyncio
from typing import List
from api_management import get_supabase_client
from utils import generate_unique_name
from crawl4ai import AsyncWebCrawler
import json
import subprocess
import sys
import streamlit as st
import os

supabase = get_supabase_client()

async def get_fit_markdown_async(url: str) -> str:
    """
    Async function using crawl4ai's AsyncWebCrawler to produce the regular raw markdown.
    (Reverting from the 'fit' approach back to normal.)
    """
    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            if result.success:
                return result.markdown
            else:
                return ""
    except Exception as e:
        # Check if the error message contains the Playwright installation message
        error_str = str(e)
        if "Executable doesn't exist" in error_str and "playwright install" in error_str:
            return "PLAYWRIGHT_INSTALL_NEEDED"
        else:
            st.error(f"Error scraping URL: {e}")
            return ""


def fetch_fit_markdown(url: str) -> str:
    """
    Synchronous wrapper around get_fit_markdown_async().
    Handles Playwright installation if needed.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(get_fit_markdown_async(url))
        
        # Check if we need to install Playwright browsers
        if result == "PLAYWRIGHT_INSTALL_NEEDED":
            st.error("""
            Playwright browsers are not installed. Please run the following command in your terminal:
            
            ```
            playwright install
            ```
            
            Then restart the application.
            """)
            return ""
                
        return result
    finally:
        loop.close()

def read_raw_data(unique_name: str) -> str:
    """
    Query the 'scraped_data' table for the row with this unique_name,
    and return the 'raw_data' field.
    """
    if supabase is None:
        print("Warning: Supabase client is not initialized. Check your credentials.")
        return None
        
    response = supabase.table("scraped_data").select("raw_data").eq("unique_name", unique_name).execute()
    data = response.data
    if data and len(data) > 0:
        raw_data = data[0]["raw_data"]
        # If raw_data is a string, try to parse it as JSON
        if isinstance(raw_data, str):
            try:
                return json.loads(raw_data)
            except json.JSONDecodeError:
                return raw_data
        return raw_data
    return None

def save_raw_data(unique_name: str, url: str, raw_data: str) -> None:
    """
    Save or update the row in supabase with unique_name, url, and raw_data.
    If a row with unique_name doesn't exist, it inserts; otherwise it might upsert.
    """
    # If raw_data is a string, try to parse it as JSON
    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except json.JSONDecodeError:
            # If it's not valid JSON, keep it as a string
            pass
    
    supabase.table("scraped_data").upsert({
        "unique_name": unique_name,
        "url": url,
        "raw_data": raw_data
    }, on_conflict="id").execute()
    BLUE = "\033[34m"
    RESET = "\033[0m"
    print(f"{BLUE}INFO:Raw data stored for {unique_name}{RESET}")

def fetch_and_store_markdowns(urls: List[str]) -> List[str]:
    """
    For each URL:
      1) Generate unique_name
      2) Check if there's already a row in supabase with that unique_name
      3) If not found or if raw_data is empty, fetch fit_markdown
      4) Save to supabase
    Return a list of unique_names (one per URL).
    """
    unique_names = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_urls = len(urls)
    for i, url in enumerate(urls):
        try:
            # Update progress
            progress = (i / total_urls)
            progress_bar.progress(progress)
            status_text.text(f"Processing URL {i+1}/{total_urls}: {url[:40]}...")
            
            unique_name = generate_unique_name(url)
            MAGENTA = "\033[35m"
            RESET = "\033[0m"
            # check if we already have raw_data in supabase
            raw_data = read_raw_data(unique_name)
            if raw_data:
                print(f"{MAGENTA}Found existing data in supabase for {url} => {unique_name}{RESET}")
            else:
                # fetch fit markdown
                status_text.text(f"Scraping content from URL {i+1}/{total_urls}: {url[:40]}...")
                fit_md = fetch_fit_markdown(url)
                if fit_md:
                    save_raw_data(unique_name, url, fit_md)
                else:
                    st.warning(f"Could not scrape content from {url}. Skipping.")
            unique_names.append(unique_name)
        except Exception as e:
            st.error(f"Error processing URL {url}: {str(e)}")
            # Still add the unique name to keep the list consistent
            unique_name = generate_unique_name(url)
            unique_names.append(unique_name)

    # Clear the progress indicators
    progress_bar.empty()
    status_text.empty()
    
    return unique_names
