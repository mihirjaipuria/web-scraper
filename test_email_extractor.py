"""
Unit tests for the email_extractor module
"""

import unittest
from email_extractor import (
    extract_emails_from_html,
    _extract_emails_with_regex,
    _extract_emails_from_mailto,
    _extract_obfuscated_emails,
    _is_valid_email
)

class TestEmailExtractor(unittest.TestCase):
    
    def test_basic_email_extraction(self):
        """Test extraction of plaintext emails."""
        html = """
        <p>Contact us at support@example.com for more information.</p>
        <p>Or email our team at team@example.org.</p>
        """
        emails = extract_emails_from_html(html)
        self.assertIn("support@example.com", emails)
        self.assertIn("team@example.org", emails)
        
    def test_mailto_extraction(self):
        """Test extraction of emails from mailto links."""
        html = """
        <a href="mailto:contact@example.com">Email us</a>
        <a href="mailto:info@example.org?subject=Question">Questions</a>
        """
        emails = extract_emails_from_html(html)
        self.assertIn("contact@example.com", emails)
        self.assertIn("info@example.org", emails)
        
    def test_entity_encoded_extraction(self):
        """Test extraction of emails with HTML entity encoding."""
        html = """
        <p>Reach out to john&#64;example.com for support.</p>
        """
        emails = extract_emails_from_html(html)
        self.assertIn("john@example.com", emails)
        
    def test_javascript_obfuscation(self):
        """Test extraction of emails obfuscated with JavaScript."""
        html = """
        <script>
        var email = "user" + "@" + "example.com";
        document.write('<a href="mailto:' + email + '">' + email + '</a>');
        </script>
        """
        emails = extract_emails_from_html(html)
        self.assertIn("user@example.com", emails)
        
    def test_data_attribute_obfuscation(self):
        """Test extraction of emails using data attributes."""
        html = """
        <span data-name="contact" data-domain="example.com"></span>
        <span data-email="info@example.org"></span>
        """
        emails = extract_emails_from_html(html)
        self.assertIn("contact@example.com", emails)
        self.assertIn("info@example.org", emails)
        
    def test_academic_page(self):
        """Test extraction from an academic page-like structure."""
        html = """
        <title>Prof. Jane Smith | University Profile</title>
        <h1>Jane Smith</h1>
        <p>Department of Computer Science, XYZ University</p>
        <p>Faculty Email: faculty-no-reply@xyz.edu</p>
        """
        emails = extract_emails_from_html(html)
        self.assertTrue(any("jane" in email.lower() for email in emails) or 
                       any("smith" in email.lower() for email in emails) or
                       "faculty-no-reply@xyz.edu" in emails)
        
    def test_invalid_emails_filtered(self):
        """Test that invalid emails are filtered out."""
        html = """
        <p>This is not an email: @example.com</p>
        <p>Neither is this: john@</p>
        <p>This is valid: john.doe@example.com</p>
        """
        emails = extract_emails_from_html(html)
        self.assertNotIn("@example.com", emails)
        self.assertNotIn("john@", emails)
        self.assertIn("john.doe@example.com", emails)

if __name__ == "__main__":
    unittest.main() 