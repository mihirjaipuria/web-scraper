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
    """Returns a Supabase client using credentials from environment variables."""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_ANON_KEY')

    if not supabase_url or not supabase_key or "your-supabase-url-here" in supabase_url:
        return None

    return create_client(supabase_url, supabase_key)
