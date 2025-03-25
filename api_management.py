import streamlit as st
from supabase import create_client

def get_api_key(model):
    """
    Returns the OpenAI API key from Streamlit secrets.
    """
    return st.secrets["OPENAI_API_KEY"]

def get_supabase_client():
    """Returns a Supabase client using credentials from Streamlit secrets."""
    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_ANON_KEY"]

        if not supabase_url or not supabase_key or "your-supabase-url-here" in supabase_url:
            return None

        return create_client(supabase_url, supabase_key)
    except Exception as e:
        st.error(f"Error connecting to Supabase: {e}")
        return None
