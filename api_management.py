import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
def get_api_key(model):
    """
    Returns the OpenAI API key from the environment variables.
    """
    return os.getenv("OPENAI_API_KEY")

def get_supabase_client():
    """Returns a Supabase client using credentials from environment variables or Streamlit secrets."""
    # First try to get from environment variables
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')
    
    # If not in env vars, try to get from Streamlit secrets
    if not supabase_url or not supabase_key or "your-supabase-url-here" in supabase_url:
        try:
            supabase_url = st.secrets["SUPABASE_URL"]
            supabase_key = st.secrets["SUPABASE_ANON_KEY"]
        except (KeyError, FileNotFoundError):
            # Handle cases where secrets are not available
            pass

    if not supabase_url or not supabase_key or "your-supabase-url-here" in supabase_url:
        print("Supabase credentials not found in environment variables or Streamlit secrets.")
        return None

    return create_client(supabase_url, supabase_key)
