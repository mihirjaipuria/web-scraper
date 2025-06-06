# pagination.py

import json
import re
from typing import List, Dict, Tuple, Optional, Any
from assets import PROMPT_PAGINATION
from markdown import read_raw_data, fetch_and_store_markdowns
from api_management import get_supabase_client
from pydantic import BaseModel, Field
from typing import List
from pydantic import create_model
from llm_calls import (call_llm_model)
from scraper import scrape_urls, extract_and_add_emails

supabase = get_supabase_client()


class PaginationModel(BaseModel):
    page_urls: List[str]


def get_pagination_response_format():
    return PaginationModel


def create_dynamic_listing_model(field_names: List[str]):
    field_definitions = {field: (str, ...) for field in field_names}
    return create_model('DynamicListingModel', **field_definitions)

def build_pagination_prompt(indications: str, url: str) -> str:
    # Base prompt
    prompt = PROMPT_PAGINATION + f"\nThe page being analyzed is: {url}\n"

    if indications.strip():
        prompt += (
            "These are the user's indications. Pay attention:\n"
            f"{indications}\n\n"
        )
    else:
        prompt += (
            "No special user indications. Just apply the pagination logic.\n\n"
        )
    # Finally append the actual markdown data
    return prompt


def save_pagination_data(unique_name: str, pagination_data):
       # if it's a pydantic object, convert to dict
    if hasattr(pagination_data, "dict"):
        pagination_data = pagination_data.dict()
    
    # parse if string
    if isinstance(pagination_data, str):
        try:
            pagination_data = json.loads(pagination_data)
        except json.JSONDecodeError:
            pagination_data = {"raw_text": pagination_data}

    supabase.table("scraped_data").update({
        "pagination_data": pagination_data
    }).eq("unique_name", unique_name).execute()
    MAGENTA = "\033[35m"
    RESET = "\033[0m" 
    print(f"{MAGENTA}INFO:Pagination data saved for {unique_name}{RESET}")

def is_likely_first_page(url: str) -> bool:
    """
    Determine if a URL is likely the first page of content.
    This function uses heuristics to detect page 1 even without explicit page numbers.
    
    Args:
        url: URL to check
    
    Returns:
        True if the URL is likely page 1, False otherwise
    """
    # Check for explicit page 1 markers
    page_number = extract_page_number(url)
    if page_number == 1:
        return True
    
    # Check for common patterns that indicate a base/first page
    # 1. Base domain with no pagination parameters
    if re.match(r'^https?://[^/]+/?$', url):
        return True
    
    # 2. URLs ending with / or common index files
    if re.search(r'/$|/index\.(?:html|php|asp|jsp)$', url):
        return True
    
    # 3. No pagination parameters at all
    if not any(param in url for param in ['page=', '/page/', '?p=', '&p=']):
        return True
    
    return False

def paginate_urls(unique_names: List[str], selected_model: str, indication: str, urls:List[str], fields: List[str]=None, auto_scrape_pages: bool=True, start_page: int=1, end_page: int=None):
    """
    For each unique_name, read raw_data, detect pagination, save results,
    accumulate cost usage, and return a final summary.
    
    Args:
        unique_names: List of unique identifiers for each URL
        selected_model: The LLM model to use
        indication: User-provided instructions about pagination
        urls: List of URLs corresponding to the unique names
        fields: Fields to extract when scraping paginated URLs
        auto_scrape_pages: Whether to automatically scrape the paginated pages
        start_page: Starting page number to scrape (default: 1)
        end_page: Ending page number to scrape (default: None, scrape all pages)
        
    Returns:
        Total input tokens, output tokens, cost, and pagination results
    """
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0
    pagination_results = []
    all_paginated_data = []

    # Track original URLs to avoid duplicates
    original_urls = set(urls)
    
    # Check if any of the original URLs are page 1
    original_has_page_1 = False
    for url in urls:
        if is_likely_first_page(url):
            original_has_page_1 = True
            print(f"\033[34mMain URL is detected as page 1: {url}\033[0m")
            break

    # First extract pagination URLs from all pages
    for uniq, current_url in zip(unique_names, urls):
        raw_data = read_raw_data(uniq)
        if not raw_data:
            print(f"No raw_data found for {uniq}, skipping pagination.")
            continue
        
        # Adjust pagination range if original URL is page 1
        effective_start_page = start_page
        if original_has_page_1 and start_page == 1:
            # Skip page 1 in pagination since it's already in the original URLs
            effective_start_page = 2
            print(f"\033[34mAdjusting pagination to start from page 2 since page 1 is in main URLs\033[0m")
        
        # Add pagination range information to the prompt
        pagination_range_info = f"Extract pagination URLs only within this range: starting from page {effective_start_page}"
        if end_page is not None:
            pagination_range_info += f" up to page {end_page}"
        pagination_range_info += "."
        
        full_indication = indication + "\n" + pagination_range_info if indication.strip() else pagination_range_info
        
        response_schema = get_pagination_response_format()
        prompt = build_pagination_prompt(full_indication, current_url)
        pag_data, token_counts, cost = call_llm_model(raw_data, response_schema, selected_model, prompt)

        # Store pagination data
        save_pagination_data(uniq, pag_data)

        # Accumulate cost
        total_input_tokens += token_counts["input_tokens"]
        total_output_tokens += token_counts["output_tokens"]
        total_cost += cost
        print(f"\033[36mPagination Cost for {uniq}: ${cost:.6f}\033[0m")

        pagination_results.append({"unique_name": uniq, "pagination_data": pag_data})
        
    # Now, if auto_scrape_pages is True and we have fields to extract, scrape all paginated URLs
    if auto_scrape_pages and fields:
        print(f"\033[34mAuto-scraping enabled. Beginning to process pagination pages...\033[0m")
        
        # Collect all pagination URLs from all results
        all_page_urls = []
        for page_info in pagination_results:
            # Get the pagination_data which contains page_urls
            pagination_data = page_info.get("pagination_data", {})
            
            # Convert to dict if it's a Pydantic model
            if hasattr(pagination_data, "dict"):
                pagination_data = pagination_data.dict()
            elif isinstance(pagination_data, str):
                try:
                    pagination_data = json.loads(pagination_data)
                except json.JSONDecodeError:
                    pagination_data = {}
            
            # Extract page_urls if available
            if isinstance(pagination_data, dict) and "page_urls" in pagination_data:
                page_urls = pagination_data.get("page_urls", [])
                if isinstance(page_urls, list):
                    # Determine effective start page (skip page 1 if it's in the original URLs)
                    effective_start = start_page
                    if original_has_page_1 and start_page == 1:
                        # If the main URL is already page 1, start from page 2
                        effective_start = 2
                        # Filter out all page 1 URLs to avoid duplication
                        page_urls = [url for url in page_urls if not (extract_page_number(url) == 1 or 
                                                                    (extract_page_number(url) is None and is_likely_first_page(url)))]
                    
                    # Filter URLs based on the effective page number range
                    filtered_urls = filter_urls_by_page_range(page_urls, effective_start, end_page)
                    
                    # Filter out original URLs to avoid duplicates
                    filtered_urls = [url for url in filtered_urls if url not in original_urls]
                    
                    # Log the detected URLs
                    print(f"\033[34mDetected {len(filtered_urls)} unique pagination URLs within range for {page_info.get('unique_name')}\033[0m")
                    all_page_urls.extend(filtered_urls)
        
        if all_page_urls:
            # Remove duplicates while preserving order
            unique_page_urls = []
            seen_urls = set()
            for url in all_page_urls:
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_page_urls.append(url)
                    
            print(f"\033[34mBeginning to scrape {len(unique_page_urls)} unique pagination URLs\033[0m")
            
            # Fetch and store content for all pagination URLs
            print("\033[34mFetching content for pagination URLs...\033[0m")
            page_unique_names = fetch_and_store_markdowns(unique_page_urls)
            
            if page_unique_names:
                print(f"\033[34mSuccessfully fetched {len(page_unique_names)} pagination pages\033[0m")
                
                # Scrape data from each pagination page
                print("\033[34mExtracting data from pagination pages...\033[0m")
                page_in_tokens, page_out_tokens, page_cost, page_data = scrape_urls(
                    page_unique_names,
                    fields,
                    selected_model
                )
                
                # Apply email extraction to pagination results if not already done in scrape_urls
                for data_item in page_data:
                    unique_name = data_item.get("unique_name")
                    parsed_data = data_item.get("parsed_data")
                    if unique_name and parsed_data:
                        # Email extraction is now handled within scrape_urls
                        pass
                
                # Add to total tokens and cost
                total_input_tokens += page_in_tokens
                total_output_tokens += page_out_tokens
                total_cost += page_cost
                
                # Store the paginated data
                all_paginated_data = page_data
                
                print(f"\033[32mSuccessfully scraped data from {len(page_data)} pagination pages\033[0m")
                
                # Add pagination source information to the results
                for data_item in all_paginated_data:
                    if isinstance(data_item, dict):
                        data_item["pagination_source"] = True
                    else:
                        # If data_item is not a dict, try to convert it
                        try:
                            if isinstance(data_item, str):
                                data_dict = json.loads(data_item)
                                data_dict["pagination_source"] = True
                                # Replace the string with the dict
                                i = all_paginated_data.index(data_item)
                                all_paginated_data[i] = data_dict
                            elif hasattr(data_item, 'dict'):
                                # If it's a pydantic model
                                data_dict = data_item.dict()
                                data_dict["pagination_source"] = True
                                # Replace the model with the dict
                                i = all_paginated_data.index(data_item)
                                all_paginated_data[i] = data_dict
                        except (json.JSONDecodeError, ValueError, AttributeError) as e:
                            print(f"\033[31mError processing pagination data item: {str(e)}\033[0m")
            else:
                print("\033[33mNo content was retrieved from pagination URLs\033[0m")
        else:
            print("\033[33mNo pagination URLs found to scrape\033[0m")
    
    # Add the paginated data to the return value
    pagination_summary = {
        "pagination_info": pagination_results,
        "paginated_data": all_paginated_data
    }
    
    print(f"\033[33m=== Pagination Summary ===\033[0m")
    print(f"\033[33mTotal Pages Detected: {sum(len(item.get('pagination_data', {}).get('page_urls', [])) for item in pagination_results if isinstance(item.get('pagination_data', {}), dict))}\033[0m")
    print(f"\033[33mTotal Pages Scraped: {len(all_paginated_data)}\033[0m")
    print(f"\033[33mTotal Input Tokens: {total_input_tokens}\033[0m")
    print(f"\033[33mTotal Output Tokens: {total_output_tokens}\033[0m")
    print(f"\033[33mTotal Pagination Cost: ${total_cost:.6f}\033[0m")
    
    return total_input_tokens, total_output_tokens, total_cost, pagination_summary

def scrape_pagination_results(pagination_info, fields, selected_model):
    """
    Scrapes data from all pagination links found.
    
    Args:
        pagination_info: List of pagination results containing page URLs
        fields: Fields to extract from each page
        selected_model: Model to use for extraction
        
    Returns:
        Combined extracted data from all pagination pages, with token and cost info
    """
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0
    all_pagination_data = []
    
    # Collect all pagination URLs from the pagination_info
    all_pagination_urls = []
    
    for page_info in pagination_info:
        # Get the pagination_data which contains page_urls
        pagination_data = page_info.get("pagination_data", {})
        
        # Convert to dict if it's a Pydantic model
        if hasattr(pagination_data, "dict"):
            pagination_data = pagination_data.dict()
        elif isinstance(pagination_data, str):
            try:
                pagination_data = json.loads(pagination_data)
            except json.JSONDecodeError:
                pagination_data = {}
        
        # Extract page_urls if available
        if isinstance(pagination_data, dict) and "page_urls" in pagination_data:
            page_urls = pagination_data.get("page_urls", [])
            if isinstance(page_urls, list):
                all_pagination_urls.extend(page_urls)
    
    if not all_pagination_urls:
        print("\033[33mNo pagination URLs found to scrape\033[0m")
        return total_input_tokens, total_output_tokens, total_cost, []
    
    print(f"\033[34mBeginning to scrape {len(all_pagination_urls)} pagination URLs\033[0m")
    
    # Fetch and store markdowns for all pagination URLs
    unique_names = fetch_and_store_markdowns(all_pagination_urls)
    
    # Scrape data from each pagination page
    if unique_names:
        in_tokens, out_tokens, cost, parsed_data = scrape_urls(
            unique_names,
            fields,
            selected_model
        )
        
        # Add to total tokens and cost
        total_input_tokens += in_tokens
        total_output_tokens += out_tokens
        total_cost += cost
        
        # Add to combined results
        all_pagination_data.extend(parsed_data)
        
        print(f"\033[32mSuccessfully scraped data from {len(parsed_data)} pagination pages\033[0m")
    
    print(f"\033[33m=== Pagination Scraping Summary ===\033[0m")
    print(f"\033[33mTotal Pages Scraped: {len(all_pagination_data)}\033[0m")
    print(f"\033[33mTotal Input Tokens: {total_input_tokens}\033[0m")
    print(f"\033[33mTotal Output Tokens: {total_output_tokens}\033[0m")
    print(f"\033[33mTotal Pagination Scraping Cost: ${total_cost:.6f}\033[0m")
    
    return total_input_tokens, total_output_tokens, total_cost, all_pagination_data

def parse_faculty_count(prompt: str) -> int:
    """
    Parse the number of faculty members specified in a prompt.
    Returns a default of 5 if no number is found.
    
    Args:
        prompt: The user search prompt
        
    Returns:
        The number of faculty members to extract
    """
    # Look for patterns like "find me 10 faculty" or "get 5 professors"
    match = re.search(r"(\d+)\s+(?:faculty|professors|researchers|academics)", prompt, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 5  # Default count if no number specified

def generate_search_urls(university_name: str, count: int = 5) -> List[str]:
    """
    Generate search URLs for faculty profiles based on university name
    
    Args:
        university_name: Name of the university to search for
        count: Number of results to target
        
    Returns:
        List of generated search URLs
    """
    search_urls = []
    
    # Create a standard Google search URL for faculty directory
    cleaned_name = university_name.strip().replace(" ", "+")
    search_urls.append(f"https://www.google.com/search?q={cleaned_name}+faculty+directory")
    
    # If looking for a specific department, could add specialized URLs
    search_urls.append(f"https://www.google.com/search?q={cleaned_name}+professor+profiles")
    
    return search_urls

def extract_faculty_count(faculty_profiles: List[Dict], count: int, criteria: Optional[str] = None) -> Tuple[List[Dict], int, float]:
    """
    Extract a specific number of faculty profiles based on prompt
    
    Args:
        faculty_profiles: List of faculty profile data
        count: Number of profiles to extract
        criteria: Optional criteria for selecting profiles
        
    Returns:
        List of selected faculty members, token counts, and cost
    """
    total_tokens = 0
    total_cost = 0.0
    
    # If we have fewer results than requested count, return all
    if len(faculty_profiles) <= count:
        return faculty_profiles, total_tokens, total_cost
    
    # If there's a specific selection criteria, we would filter based on that
    if criteria:
        # This could involve more complex filtering logic based on the criteria
        # For now, just return the first 'count' profiles
        selected_profiles = faculty_profiles[:count]
    else:
        # Simple case: just take the first 'count' profiles
        selected_profiles = faculty_profiles[:count]
    
    return selected_profiles, total_tokens, total_cost

def search_faculty_by_prompt(faculty_profiles: List[Dict], prompt: str) -> List[Dict]:
    """
    Filter faculty profiles based on user-defined criteria in natural language
    
    Args:
        faculty_profiles: List of faculty profile data
        prompt: Natural language prompt describing search criteria
        
    Returns:
        Filtered list of faculty profiles matching the criteria
    """
    if not prompt or not faculty_profiles:
        return faculty_profiles
    
    # This is a simplified implementation
    # In a real implementation, you would:
    # 1. Use an embedding model to compare the prompt with faculty profiles
    # 2. Or use a language model to evaluate each profile against the criteria
    
    # For now, we'll do basic keyword matching
    prompt = prompt.lower()
    filtered_profiles = []
    
    for profile in faculty_profiles:
        # Convert profile to string for simple matching
        profile_text = json.dumps(profile).lower()
        
        # Check if any keywords from the prompt are in the profile
        if any(keyword in profile_text for keyword in prompt.split()):
            # Add a reason for the match
            profile_copy = profile.copy()
            profile_copy["match_reason"] = f"Matched search terms in prompt: '{prompt}'"
            filtered_profiles.append(profile_copy)
    
    return filtered_profiles

def filter_urls_by_page_range(urls: List[str], start_page: int, end_page: int = None) -> List[str]:
    """
    Filter URLs based on page numbers in the range [start_page, end_page].
    If end_page is None, include all pages from start_page onwards.
    
    Args:
        urls: List of URLs to filter
        start_page: Starting page number (inclusive)
        end_page: Ending page number (inclusive), or None for all pages
    
    Returns:
        List of URLs that match the specified page range
    """
    filtered_urls = []
    seen_page_numbers = set()  # Track page numbers we've already seen
    
    print(f"\033[35mFiltering {len(urls)} URLs for pages {start_page}-{end_page if end_page else 'end'}\033[0m")
    
    for url in urls:
        # Try to extract page number from URL
        page_number = extract_page_number(url)
        
        if page_number is not None:
            # Skip if we've already seen this page number
            if page_number in seen_page_numbers:
                print(f"\033[35mSkipping duplicate page {page_number}: {url}\033[0m")
                continue
                
            if end_page is not None:
                if start_page <= page_number <= end_page:
                    print(f"\033[35mIncluding page {page_number} (in range {start_page}-{end_page}): {url}\033[0m")
                    filtered_urls.append(url)
                    seen_page_numbers.add(page_number)
                else:
                    print(f"\033[35mSkipping page {page_number} (outside range {start_page}-{end_page}): {url}\033[0m")
            else:
                if page_number >= start_page:
                    print(f"\033[35mIncluding page {page_number} (>= {start_page}): {url}\033[0m")
                    filtered_urls.append(url)
                    seen_page_numbers.add(page_number)
                else:
                    print(f"\033[35mSkipping page {page_number} (< {start_page}): {url}\033[0m")
        else:
            # If page number can't be determined, include the URL
            # This ensures we don't miss important URLs
            print(f"\033[35mIncluding URL with no page number detected: {url}\033[0m")
            filtered_urls.append(url)
    
    print(f"\033[35mFiltered to {len(filtered_urls)} URLs in range\033[0m")
    return filtered_urls

def extract_page_number(url: str) -> Optional[int]:
    """
    Extract page number from a URL.
    
    Args:
        url: URL to extract page number from
    
    Returns:
        Page number as integer, or None if not found
    """
    # Common patterns for page numbers in URLs
    patterns = [
        r'[?&]page=(\d+)',           # ?page=X or &page=X
        r'[?&]p=(\d+)',              # ?p=X or &p=X
        r'[?&]pg=(\d+)',             # ?pg=X or &pg=X
        r'[?&]paged=(\d+)',          # ?paged=X or &paged=X
        r'[?&]paging=(\d+)',         # ?paging=X or &paging=X
        r'[?&]pp=(\d+)',             # ?pp=X or &pp=X
        r'[?&]pagina=(\d+)',         # ?pagina=X or &pagina=X (Spanish/Italian)
        r'[?&]seite=(\d+)',          # ?seite=X or &seite=X (German)
        r'[?&]pagine=(\d+)',         # ?pagine=X or &pagine=X
        r'[?&]pagination=(\d+)',     # ?pagination=X
        r'[?&]current=(\d+)',        # ?current=X or &current=X
        r'[?&]offset=(\d+)',         # ?offset=X or &offset=X
        r'/page/(\d+)',              # /page/X
        r'/p/(\d+)',                 # /p/X
        r'/paged/(\d+)',             # /paged/X
        r'/pages/(\d+)',             # /pages/X
        r'-page-(\d+)',              # -page-X
        r'_page_(\d+)',              # _page_X
        r'-p-(\d+)',                 # -p-X
        r'_p_(\d+)',                 # _p_X
        r'[\-_](\d+)\.html',         # -X.html or _X.html
        r'/(\d+)/?$',                # /X/ at end of URL
        r'page(\d+)\.html',          # pageX.html
        r'p(\d+)\.html',             # pX.html
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            try:
                page_num = int(match.group(1))
                # Print diagnostic info for debugging
                # print(f"\033[35mExtracted page number {page_num} from URL: {url} using pattern: {pattern}\033[0m")
                return page_num
            except ValueError:
                pass
    
    # If no page number found, default to None
    # print(f"\033[35mNo page number found in URL: {url}\033[0m")
    return None
