# scraper.py

import json
from typing import List, Dict, Any
from pydantic import BaseModel, create_model
from assets import (OPENAI_MODEL_FULLNAME,SYSTEM_MESSAGE)
from llm_calls import (call_llm_model)
from markdown import read_raw_data
from api_management import get_supabase_client
from utils import  generate_unique_name
from email_extractor import extract_emails_from_html

supabase = get_supabase_client()

def create_dynamic_listing_model(field_names: List[str]):
    if 'email' not in field_names:
        field_names.append('email')
    field_definitions = {field: (str, ...) for field in field_names}
    return create_model('DynamicListingModel', **field_definitions)

def create_listings_container_model(listing_model: BaseModel):
    return create_model('DynamicListingsContainer', listings=(List[listing_model], ...))

def generate_system_message(listing_model: BaseModel) -> str:
    # same logic as your code
    schema_info = listing_model.model_json_schema()
    field_descriptions = []
    for field_name, field_info in schema_info["properties"].items():
        field_type = field_info["type"]
        field_descriptions.append(f'"{field_name}": "{field_type}"')

    schema_structure = ",\n".join(field_descriptions)

    final_prompt= SYSTEM_MESSAGE+"\n"+f"""strictly follows this schema:
    {{
       "listings": [
         {{
           {schema_structure}
         }}
       ]
    }}
    """

    return final_prompt


def save_formatted_data(unique_name: str, formatted_data):
    """
    Save formatted data to Supabase.
    Handles various data types including strings, dictionaries, and Pydantic models.
    """
    try:
        if isinstance(formatted_data, str):
            try:
                data_json = json.loads(formatted_data)
            except json.JSONDecodeError:
                data_json = {"raw_text": formatted_data}
        elif hasattr(formatted_data, "dict"):
            data_json = formatted_data.dict()
        elif isinstance(formatted_data, dict):
            data_json = formatted_data
        else:
            data_json = {"raw_text": str(formatted_data)}

        supabase.table("scraped_data").update({
            "formatted_data": data_json
        }).eq("unique_name", unique_name).execute()
        
        MAGENTA = "\033[35m"
        RESET = "\033[0m"  # Reset color to default
        print(f"{MAGENTA}INFO:Scraped data saved for {unique_name}{RESET}")
    except Exception as e:
        print(f"\033[31mERROR:Failed to save formatted data for {unique_name}: {str(e)}{RESET}")

def extract_and_add_emails(unique_name: str, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract emails from the raw HTML content and add them to the parsed data.
    
    Args:
        unique_name: The unique identifier for the scraped data
        parsed_data: The data parsed by the LLM
        
    Returns:
        Updated parsed data with email addresses
    """
    # If parsed_data is a string, try to parse it as JSON
    if isinstance(parsed_data, str):
        try:
            parsed_data = json.loads(parsed_data)
        except json.JSONDecodeError:
            return parsed_data
    
    raw_data = read_raw_data(unique_name)
    if not raw_data:
        return parsed_data
    
    extracted_emails = extract_emails_from_html(raw_data)
    
    if extracted_emails and isinstance(parsed_data, dict) and "listings" in parsed_data:
        for listing in parsed_data["listings"]:
            if isinstance(listing, dict):
                if "email" in listing and listing["email"] and listing["email"] != "N/A":
                    continue
                    
                if extracted_emails:
                    listing["email"] = extracted_emails[0]
                else:
                    listing["email"] = "N/A"
    
    return parsed_data

def scrape_urls(unique_names: List[str], fields: List[str], selected_model: str):
    """
    For each unique_name:
      1) read raw_data from supabase
      2) parse with selected LLM
      3) extract emails from raw HTML
      4) save formatted_data
      5) accumulate cost
    Return total usage + list of final parsed data
    """
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0
    parsed_results = []

    DynamicListingModel = create_dynamic_listing_model(fields)
    DynamicListingsContainer = create_listings_container_model(DynamicListingModel)

    for uniq in unique_names:
        raw_data = read_raw_data(uniq)
        if not raw_data:
            BLUE = "\033[34m"
            RESET = "\033[0m"
            print(f"{BLUE}No raw_data found for {uniq}, skipping.{RESET}")
            continue

        parsed, token_counts, cost = call_llm_model(raw_data, DynamicListingsContainer, selected_model, SYSTEM_MESSAGE)
        
        if parsed:
            # If parsed is a string, try to parse it as JSON
            if isinstance(parsed, str):
                try:
                    parsed = json.loads(parsed)
                except json.JSONDecodeError:
                    parsed = {"raw_text": parsed}
            
            parsed = extract_and_add_emails(uniq, parsed)
            save_formatted_data(uniq, parsed)

            total_input_tokens += token_counts["input_tokens"]
            total_output_tokens += token_counts["output_tokens"]
            total_cost += cost
            print(f"\033[32mScraping Cost for {uniq}: ${cost:.6f}\033[0m")
            parsed_results.append({"unique_name": uniq, "parsed_data": parsed})
    
    print(f"\033[33m=== Scraping Summary ===\033[0m")
    print(f"\033[33mTotal Input Tokens: {total_input_tokens}\033[0m")
    print(f"\033[33mTotal Output Tokens: {total_output_tokens}\033[0m")
    print(f"\033[33mTotal Scraping Cost: ${total_cost:.6f}\033[0m")

    return total_input_tokens, total_output_tokens, total_cost, parsed_results
