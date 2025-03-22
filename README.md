# 1. Create a virtual environment
python -m venv venv

# 2. Activate the virtual environment
# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

#if there are any errors in the instalation please install every library in the requirements.txt


# 4. *********     IMPORTANT     ********
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
        
        5. **Create a `.env` file** with these values (use `.env.example` as a template):
        
        ```
        SUPABASE_URL=your_supabase_url_here
        SUPABASE_ANON_KEY=your_supabase_anon_key_here
        ```

        6. **Restart the project** and you're good to go! 🚀


## 5. run "playwright install"

## 6. add your api keys in .env files for the models (you can also add them in the app)

## 7. type the command "streamlit run streamlit_app.py" in your project terminal

## 8. Enjoy the working app

## Features

### Pagination Support
The app now includes enhanced pagination support:

1. **Automatic Pagination Detection**: The system identifies pagination patterns on web pages
2. **Auto-Scraping Paginated Content**: When pagination is enabled, the app automatically:
   - Extracts pagination URLs from the initial page
   - Visits each paginated page
   - Scrapes data from all pages using the same field extraction settings
   - Combines all results into a single dataset

To use pagination:
1. Enable the "Enable Pagination" toggle in the sidebar
2. Optionally provide pagination details to help guide the extraction
3. The app will detect pagination URLs and automatically scrape all pages

Results from paginated pages are clearly marked in the data display.

## Hosting Information

### Environment Variables for Hosting
When deploying this application, you need to configure environment variables on your hosting platform:

1. **Required Environment Variables:**
   - `SUPABASE_URL` - Your Supabase project URL
   - `SUPABASE_ANON_KEY` - Your Supabase anonymous key
   - `OPENAI_API_KEY` - Your OpenAI API key (if using OpenAI models)

2. **How to Set Environment Variables on Different Platforms:**

   **Streamlit Cloud:**
   - Go to your app settings
   - Navigate to "Secrets"
   - Add each variable in the format:
     ```
     SUPABASE_URL = "your_url_here"
     SUPABASE_ANON_KEY = "your_key_here"
     ```

   **Heroku:**
   - Use the Heroku Dashboard or CLI:
     ```
     heroku config:set SUPABASE_URL=your_url_here
     heroku config:set SUPABASE_ANON_KEY=your_key_here
     ```

   **Vercel:**
   - In your project settings, find "Environment Variables"
   - Add each key-value pair

3. **Troubleshooting**:
   - If you see the Supabase setup screen, it means your environment variables aren't being loaded correctly
   - Check that the variable names exactly match those used in the code 
   - Verify you've set the variables on your hosting platform