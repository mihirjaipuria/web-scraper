"""
Email extraction utility for scraping hidden or obfuscated email addresses
from HTML content. Especially useful for academic profiles where contact
information might be protected against spam bots.
"""

import re
import html
from typing import List, Optional
from bs4 import BeautifulSoup


def extract_emails_from_html(html_content: str) -> List[str]:
    """
    Extract email addresses from HTML content using multiple extraction techniques.
    
    Args:
        html_content: Raw HTML content of the webpage
        
    Returns:
        A list of unique email addresses found
    """
    emails = set()
    
    # Method 1: Direct regex extraction from the entire HTML
    emails.update(_extract_emails_with_regex(html_content))
    
    # Method 2: Look for HTML decoded entities that might contain email parts
    decoded_html = html.unescape(html_content)
    emails.update(_extract_emails_with_regex(decoded_html))
    
    # Method 3: Parse with BeautifulSoup and look for mailto links
    emails.update(_extract_emails_from_mailto(html_content))
    
    # Method 4: Look for common email obfuscation patterns
    emails.update(_extract_obfuscated_emails(html_content))
    
    # Method 5: Check for academic domain pattern if we have the name
    try:
        name = _extract_name_from_academic_page(html_content)
        if name:
            academic_email = _generate_academic_email_pattern(name, html_content)
            if academic_email:
                emails.add(academic_email)
    except:
        # Skip this method if it fails
        pass
        
    # Filter out invalid emails
    valid_emails = [email for email in emails if _is_valid_email(email)]
    
    return valid_emails


def _extract_emails_with_regex(text: str) -> List[str]:
    """Extract emails using regex pattern matching."""
    # Standard email regex pattern
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return re.findall(email_pattern, text)


def _extract_emails_from_mailto(html_content: str) -> List[str]:
    """Extract emails from mailto: links."""
    soup = BeautifulSoup(html_content, 'html.parser')
    emails = []
    
    # Find all links with mailto:
    mailto_links = soup.select('a[href^="mailto:"]')
    for link in mailto_links:
        href = link.get('href', '')
        if 'mailto:' in href:
            email = href.split('mailto:')[1].split('?')[0].strip()
            if email:
                emails.append(email)
    
    return emails


def _extract_obfuscated_emails(html_content: str) -> List[str]:
    """Extract emails that are obfuscated with various techniques."""
    emails = []
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Method 1: Find elements with data attributes containing email parts
    elements_with_data = soup.select('[data-email], [data-name], [data-domain]')
    for element in elements_with_data:
        name = element.get('data-name', '')
        domain = element.get('data-domain', '')
        email = element.get('data-email', '')
        
        if email:
            emails.append(email)
        elif name and domain:
            emails.append(f"{name}@{domain}")
    
    # Method 2: Look for scripts that build email addresses
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and ('email' in script.string.lower() or '@' in script.string):
            # Look for patterns like "user" + "@" + "domain.com"
            email_parts = re.findall(r'[\'"]([^\'"]*)[\'"]\s*\+\s*[\'"]@[\'"]\s*\+\s*[\'"]([^\'"]*)[\'"]', script.string)
            for parts in email_parts:
                if len(parts) == 2:
                    emails.append(f"{parts[0]}@{parts[1]}")
    
    # Method 3: Look for common entity encoding &#64; for @
    encoded_at_pattern = r'([a-zA-Z0-9._%+-]+)&#64;([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    for match in re.finditer(encoded_at_pattern, html_content):
        if match and len(match.groups()) == 2:
            emails.append(f"{match.group(1)}@{match.group(2)}")
    
    return emails


def _extract_name_from_academic_page(html_content: str) -> Optional[str]:
    """Extract the person's name from an academic page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try to find the person's name (common patterns in academic pages)
    # Method 1: Look for h1 tags (often contains the person's name)
    h1_tags = soup.find_all('h1')
    for h1 in h1_tags:
        if h1.text and len(h1.text.strip()) > 0 and len(h1.text.strip().split()) <= 5:
            return h1.text.strip()
    
    # Method 2: Look for title tag
    title = soup.find('title')
    if title and 'profile' in title.text.lower():
        name_parts = title.text.split('|')[0].strip().split()
        if 1 < len(name_parts) <= 5:
            return ' '.join(name_parts)
    
    return None


def _generate_academic_email_pattern(name: str, html_content: str) -> Optional[str]:
    """Generate potential email based on name and academic context."""
    # Extract possible domain from the HTML content
    domain_match = re.search(r'@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', html_content)
    if not domain_match:
        return None
    
    domain = domain_match.group(1)
    if not domain:
        return None
    
    # Clean up the name
    name = re.sub(r'[^a-zA-Z\s]', '', name).strip().lower()
    name_parts = name.split()
    
    if len(name_parts) >= 2:
        # Common academic email patterns
        first_name = name_parts[0]
        last_name = name_parts[-1]
        
        # Try first.last@domain
        return f"{first_name}.{last_name}@{domain}"
    
    return None


def _is_valid_email(email: str) -> bool:
    """Validate email structure."""
    # Basic structural validation
    if not email or '@' not in email or '.' not in email.split('@')[1]:
        return False
    
    # Check reasonable length
    if len(email) < 5 or len(email) > 254:
        return False
    
    # Proper email regex validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email)) 