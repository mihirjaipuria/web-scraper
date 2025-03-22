# streamlit_app.py

import streamlit as st
from streamlit_tags import st_tags_sidebar
import pandas as pd
import json
import re
import sys
import asyncio
import os
# ---local imports---
from scraper import scrape_urls
from pagination import paginate_urls
from markdown import fetch_and_store_markdowns
from assets import MODELS_USED, OPENAI_MODEL_FULLNAME
from api_management import get_supabase_client

# Only use WindowsProactorEventLoopPolicy on Windows
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())



# Initialize Streamlit app
st.set_page_config(page_title="Universal Web Scraper", page_icon="🦑")
supabase=get_supabase_client()
if supabase==None:
    st.error("🚨 **Supabase is not configured!** This project requires a Supabase database to function.")
    st.warning("Follow these steps to set it up:")

    # Check if we're in a hosted environment or local environment
    is_hosted = os.environ.get("HOSTED_ENVIRONMENT") or "STREAMLIT_SHARING" in os.environ or "DYNO" in os.environ or "VERCEL" in os.environ
    
    if is_hosted:
        st.warning("⚠️ It appears you're running in a hosted environment but the Supabase credentials are missing. You need to set environment variables.")
        st.markdown("""
        ### Hosting Environment Setup:
        
        For hosted environments (Streamlit Cloud, Heroku, Vercel, etc.), you need to set environment variables:
        
        1. **Find Your Supabase Credentials**:
           - From Supabase dashboard → Project Settings → API
           - Copy your **URL** and **anon key**
           
        2. **Set Environment Variables on Your Hosting Platform**:
           - For Streamlit Cloud: Add to Secrets section
           - For Heroku: Use `heroku config:set`
           - For Vercel: Add in Environment Variables section
           
        Variables to set:
        ```
        SUPABASE_URL=your_supabase_url_here
        SUPABASE_ANON_KEY=your_supabase_anon_key_here
        ```
        
        3. **Restart your app** after setting these variables
        """)
    else:
        st.markdown("""
        1. **[Create a free Supabase account](https://supabase.com/)**.
        2. **Create a new project** inside Supabase.
        3. **Create a table** in your project by running the following SQL command in the **SQL Editor**:
        
        ```sql
        CREATE TABLE IF NOT EXISTS scraped_data (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        unique_name TEXT NOT NULL,
        url TEXT,
        raw_data JSONB,        
        formatted_data JSONB, 
        pagination_data JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW()
        );
        ```

        4. **Go to Project Settings → API** and copy:
            - **Supabase URL**
            - **Anon Key**
        
        5. **Update your `.env` file** with these values:
        
        ```
        SUPABASE_URL=your_supabase_url_here
        SUPABASE_ANON_KEY=your_supabase_anon_key_here
        ```

        6. **Restart the project** close everything and reopen it, and you're good to go! 🚀
        """)

st.title("Universal Web Scraper 🦑")

# Initialize session state variables
if 'scraping_state' not in st.session_state:
    st.session_state['scraping_state'] = 'idle'  # Possible states: 'idle', 'waiting', 'scraping', 'completed'
if 'results' not in st.session_state:
    st.session_state['results'] = None
if 'driver' not in st.session_state:
    st.session_state['driver'] = None

# Sidebar components
st.sidebar.title("Web Scraper Settings")

st.sidebar.markdown("---")
st.sidebar.write("## URL Input Section")
# Ensure the session state for our URL list exists
if "urls_splitted" not in st.session_state:
    st.session_state["urls_splitted"] = []

with st.sidebar.container():
    col1, col2 = st.columns([3, 1], gap="small")
    
    with col1:
        # A text area to paste multiple URLs at once
        if "text_temp" not in st.session_state:
            st.session_state["text_temp"] = ""

        url_text = st.text_area("Enter one or more URLs (space/tab/newline separated):",st.session_state["text_temp"], key="url_text_input", height=68)

    with col2:
        if st.button("Add URLs"):
            if url_text.strip():
                new_urls = re.split(r"\s+", url_text.strip())
                new_urls = [u for u in new_urls if u]
                st.session_state["urls_splitted"].extend(new_urls)
                st.session_state["text_temp"] = ""
                st.rerun()
        if st.button("Clear URLs"):
            st.session_state["urls_splitted"] = []
            st.rerun()

    # Show the URLs in an expander, each as a styled "bubble"
    with st.expander("Added URLs", expanded=True):
        if st.session_state["urls_splitted"]:
            bubble_html = ""
            for url in st.session_state["urls_splitted"]:
                bubble_html += (
                    f"<span style='"
                    f"background-color: #E6F9F3;"  # Very Light Mint for contrast
                    f"color: #0074D9;"            # Bright Blue for link-like appearance
                    f"border-radius: 15px;"       # Slightly larger radius for smoother edges
                    f"padding: 8px 12px;"         # Increased padding for better spacing
                    f"margin: 5px;"               # Space between bubbles
                    f"display: inline-block;"     # Ensures proper alignment
                    f"text-decoration: none;"     # Removes underline if URLs are clickable
                    f"font-weight: bold;"         # Makes text stand out
                    f"font-family: Arial, sans-serif;"  # Clean and modern font
                    f"box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);'"  # Subtle shadow for depth
                    f">{url}</span>"
                )
            st.markdown(bubble_html, unsafe_allow_html=True)
        else:
            st.write("No URLs added yet.")

st.sidebar.markdown("---")


# Fields to extract
show_tags = st.sidebar.toggle("Enable Scraping")
fields = []
if show_tags:
    fields = st_tags_sidebar(label='Enter Fields to Extract:',text='Press enter to add a field',value=[],suggestions=[],maxtags=-1,key='fields_input')

st.sidebar.markdown("---")

use_pagination = st.sidebar.toggle("Enable Pagination")
pagination_details = ""
if use_pagination:
    pagination_details = st.sidebar.text_input("Enter Pagination Details (optional)",help="Describe how to navigate through pages (e.g., 'Next' button class, URL pattern)")

st.sidebar.markdown("---")



# Main action button
if st.sidebar.button("LAUNCH", type="primary"):
    if st.session_state["urls_splitted"] == []:
        st.error("Please enter at least one URL.")
    elif show_tags and len(fields) == 0:
        st.error("Please enter at least one field to extract.")
    else:
        # Save user choices
        st.session_state['urls'] = st.session_state["urls_splitted"]
        st.session_state['fields'] = fields
        st.session_state['use_pagination'] = use_pagination
        st.session_state['pagination_details'] = pagination_details
        
        # fetch or reuse the markdown for each URL
        unique_names = fetch_and_store_markdowns(st.session_state["urls_splitted"])
        st.session_state["unique_names"] = unique_names

        # Move on to "scraping" step
        st.session_state['scraping_state'] = 'scraping'



if st.session_state['scraping_state'] == 'scraping':
    try:
        with st.spinner("Processing..."):
            unique_names = st.session_state["unique_names"]  # from the LAUNCH step

            total_input_tokens = 0
            total_output_tokens = 0
            total_cost = 0
            
            # 1) Scraping logic
            all_data = []
            if show_tags:
                in_tokens_s, out_tokens_s, cost_s, parsed_data = scrape_urls(unique_names,st.session_state['fields'],OPENAI_MODEL_FULLNAME)
                total_input_tokens += in_tokens_s
                total_output_tokens += out_tokens_s
                total_cost += cost_s

                # Store or display parsed data 
                all_data = parsed_data # or rename to something consistent
            # 2) Pagination logic
            pagination_info = None
            pagination_data = None
            if st.session_state['use_pagination']:
                in_tokens_p, out_tokens_p, cost_p, pagination_results = paginate_urls(
                    unique_names, 
                    OPENAI_MODEL_FULLNAME,
                    st.session_state['pagination_details'],
                    st.session_state["urls_splitted"],
                    fields if show_tags else None
                )
                total_input_tokens += in_tokens_p
                total_output_tokens += out_tokens_p
                total_cost += cost_p

                # Store pagination information and paginated data
                pagination_info = pagination_results.get('pagination_info', [])
                pagination_data = pagination_results.get('paginated_data', [])
                
                # Merge paginated data with regular data if available
                if pagination_data and show_tags:
                    all_data.extend(pagination_data)
                    
            # 3) Save everything in session state
            st.session_state['results'] = {
                'data': all_data,
                'input_tokens': total_input_tokens,
                'output_tokens': total_output_tokens,
                'total_cost': total_cost,
                'pagination_info': pagination_info,
                'pagination_data': pagination_data
            }
            
            # Print combined total cost
            print(f"\033[1;33m=== COMBINED TOTAL SUMMARY ===\033[0m")
            print(f"\033[1;33mTotal Input Tokens: {total_input_tokens}\033[0m")
            print(f"\033[1;33mTotal Output Tokens: {total_output_tokens}\033[0m")
            print(f"\033[1;33mTotal Combined Cost: ${total_cost:.6f}\033[0m")
            
            st.session_state['scraping_state'] = 'completed'
    except Exception as e:
        # Display the error message.
        st.error(f"An error occurred during scraping: {e}")

        # Reset the scraping state to 'idle' so that the app stays in an idle state.
        st.session_state['scraping_state'] = 'idle'

# Display results
if st.session_state['scraping_state'] == 'completed' and st.session_state['results']:
    results = st.session_state['results']
    all_data = results['data']
    total_input_tokens = results['input_tokens']
    total_output_tokens = results['output_tokens']
    total_cost = results['total_cost']
    pagination_info = results['pagination_info']
    pagination_data = results['pagination_data']

    # Display scraping details
    # Debugging snippet inside your "Scraping Results" section

    if show_tags:
        st.subheader("Scraping Results")

        # We'll accumulate all rows in this list
        all_rows = []

        # Loop over each data item in the "all_data" list
        for i, data_item in enumerate(all_data, start=1):

            # Usually data_item is something like:
            # {"unique_name": "...", "parsed_data": DynamicListingsContainer(...) or dict or str}

            # 1) Ensure data_item is a dict
            if not isinstance(data_item, dict):
                st.error(f"data_item is not a dict, skipping. Type: {type(data_item)}")
                continue

            # 2) If "parsed_data" is present and might be a Pydantic model or something
            if "parsed_data" in data_item:
                parsed_obj = data_item["parsed_data"]

                # Convert if it's a Pydantic model
                if hasattr(parsed_obj, "dict"):
                    parsed_obj = parsed_obj.model_dump()
                elif isinstance(parsed_obj, str):
                    # If it's a JSON string, attempt to parse
                    try:
                        parsed_obj = json.loads(parsed_obj)
                    except json.JSONDecodeError:
                        # fallback: just keep as raw string
                        pass

                # Now we have "parsed_obj" as a dict, list, or string
                data_item["parsed_data"] = parsed_obj

            # 3) If the "parsed_data" has a 'listings' key that is a list of items,
            #    we might want to treat them as multiple rows. 
            #    Otherwise, we treat the entire data_item as a single row.

            pd_obj = data_item["parsed_data"]

            # If it has 'listings' in parsed_data
            if isinstance(pd_obj, dict) and "listings" in pd_obj and isinstance(pd_obj["listings"], list):
                # We'll create one row per listing, plus carry over "unique_name" or other fields
                for listing in pd_obj["listings"]:
                    # Make a shallow copy so we don't mutate 'listing'
                    row_dict = dict(listing)
                    # You can also attach the unique_name or other top-level fields:
                    # row_dict["unique_name"] = data_item.get("unique_name", "")
                    all_rows.append(row_dict)
            else:
                # We'll just store the entire item as one row
                # Possibly flatten parsed_data => just store it as "parsed_data" field
                # e.g. if parsed_obj is a dict, embed it. Or keep it as string
                row_dict = dict(data_item)  # shallow copy
                all_rows.append(row_dict)

        # For each item in parsed_data, convert the pagination_source flag to a human-readable indicator
        for row in all_rows:
            if "pagination_source" in row:
                row["data_source"] = "Pagination" if row["pagination_source"] else "Main URL"
            else:
                row["data_source"] = "Main URL"

        # After collecting all rows from all_data in "all_rows", create one DataFrame
        if not all_rows:
            st.warning("No data rows to display.")
        else:
            df = pd.DataFrame(all_rows)
            
            # Configure the data_source column to be displayed with color indicators
            st.dataframe(
                df, 
                column_config={
                    "data_source": st.column_config.TextColumn(
                        "Data Source",
                        help="Indicates whether the data came from the main URL or from pagination"
                    )
                },
                use_container_width=True
            )

            # Add information about data sources
            if any("pagination_source" in row for row in all_rows):
                num_pagination_rows = sum(1 for row in all_rows if row.get("pagination_source", False))
                num_regular_rows = len(all_rows) - num_pagination_rows
                
                st.info(f"Data includes {num_regular_rows} entries from main URLs and {num_pagination_rows} entries from pagination.")

        # Download options
        st.subheader("Download Extracted Data")
        col1, col2 = st.columns(2)
        with col1:
            json_data = json.dumps(all_data, default=lambda o: o.dict() if hasattr(o, 'dict') else str(o), indent=4)
            st.download_button("Download JSON",data=json_data,file_name="scraped_data.json")
        with col2:
            # Convert all data to a single DataFrame
            all_listings = []
            for data in all_data:
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                if isinstance(data, dict) and 'listings' in data:
                    all_listings.extend(data['listings'])
                elif hasattr(data, 'listings'):
                    all_listings.extend([item.dict() for item in data.listings])
                else:
                    all_listings.append(data)
            
            combined_df = pd.DataFrame(all_listings)
            st.download_button("Download CSV",data=combined_df.to_csv(index=False),file_name="scraped_data.csv")

        st.success(f"Scraping completed. Results saved in database")

    # Display pagination info
    if pagination_info:
        st.subheader("Pagination Analysis")
        
        # Display pagination information
        total_pagination_urls = 0
        for item in pagination_info:
            if "pagination_data" in item:
                pag_obj = item["pagination_data"]

                # Convert if it's a Pydantic model
                if hasattr(pag_obj, "dict"):
                    pag_obj = pag_obj.model_dump()
                elif isinstance(pag_obj, str):
                    # If it's a JSON string, attempt to parse
                    try:
                        pag_obj = json.loads(pag_obj)
                    except json.JSONDecodeError:
                        pag_obj = {"error": "Could not parse pagination data"}
                
                # Count pagination URLs
                if isinstance(pag_obj, dict) and "page_urls" in pag_obj and isinstance(pag_obj["page_urls"], list):
                    total_pagination_urls += len(pag_obj["page_urls"])
        
        # Display summary metrics
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Pages Detected", total_pagination_urls)
        with col2:
            st.metric("Pages Scraped", len(pagination_data) if pagination_data else 0)
        
        # Display the pagination URLs in an expandable section
        with st.expander("View All Detected Pagination URLs"):
            for item in pagination_info:
                if "pagination_data" in item and "unique_name" in item:
                    st.markdown(f"**Source**: {item['unique_name']}")
                    
                    pag_obj = item["pagination_data"]
                    # Convert if needed
                    if hasattr(pag_obj, "dict"):
                        pag_obj = pag_obj.model_dump()
                    elif isinstance(pag_obj, str):
                        try:
                            pag_obj = json.loads(pag_obj)
                        except json.JSONDecodeError:
                            pag_obj = {"error": "Could not parse pagination data"}
                    
                    # Display URLs
                    if isinstance(pag_obj, dict) and "page_urls" in pag_obj and isinstance(pag_obj["page_urls"], list):
                        urls = pag_obj["page_urls"]
                        if urls:
                            st.write("Detected URLs:")
                            for url in urls:
                                st.markdown(f"- [{url}]({url})")
                        else:
                            st.write("No pagination URLs detected")
                    else:
                        st.write("No valid pagination data")
                    
                    st.markdown("---")
    # Reset scraping state
    if st.sidebar.button("Clear Results"):
        st.session_state['scraping_state'] = 'idle'
        st.session_state['results'] = None

