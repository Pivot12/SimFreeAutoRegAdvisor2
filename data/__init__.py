# Create __init__.py files to make the modules importable

# utils/__init__.py
utils_init = """
from .firecrawl_utils import fetch_regulation_data
from .cerebras_utils import process_with_llama_scout
from .regulation_utils import extract_relevant_regulations, format_regulation_response
from .mcp_handler import MCPHandler
from .logger import log_query, load_log_data, initialize_log_file, get_query_statistics

__all__ = [
    'fetch_regulation_data',
    'process_with_llama_scout',
    'extract_relevant_regulations',
    'format_regulation_response',
    'MCPHandler',
    'log_query',
    'load_log_data',
    'initialize_log_file',
    'get_query_statistics'
]
"""

# data/__init__.py
data_init = """
# This file is intentionally empty to make the 'data' directory a Python package
"""

# tests/__init__.py
tests_init = """
# This file is intentionally empty to make the 'tests' directory a Python package
"""

# Create a simple test file for firecrawl_utils
test_firecrawl = """
import unittest
from unittest.mock import patch, MagicMock
from utils.firecrawl_utils import (
    fetch_regulation_data,
    prepare_search_terms,
    scrape_website,
    crawl_website,
    extract_relevant_content
)

class TestFirecrawlUtils(unittest.TestCase):
    
    def test_prepare_search_terms(self):
        query = "What are the emissions regulations for electric vehicles in the EU?"
        terms = prepare_search_terms(query)
        
        # Check if important terms are included
        self.assertIn("emissions", terms)
        self.assertIn("regulations", terms)
        self.assertIn("electric", terms)
        self.assertIn("vehicles", terms)
        self.assertIn("eu", terms)
        
        # Check if common words are excluded
        self.assertNotIn("what", terms)
        self.assertNotIn("are", terms)
        self.assertNotIn("the", terms)
        self.assertNotIn("for", terms)
        self.assertNotIn("in", terms)
    
    @patch('utils.firecrawl_utils.scrape_website')
    @patch('utils.firecrawl_utils.crawl_website')
    @patch('utils.firecrawl_utils.extract_relevant_content')
    def test_fetch_regulation_data(self, mock_extract, mock_crawl, mock_scrape):
        # Set up mocks
        mock_scrape.return_value = {
            "markdown": "Test content",
            "metadata": {"title": "Test Title"}
        }
        mock_extract.return_value = "Relevant content"
        mock_crawl.return_value = (["Crawled content"], ["https://example.com/page"], ["Page Title"])
        
        # Call the function
        query = "Test query"
        websites = ["https://example.com"]
        api_key = "test_key"
        
        regulation_data, source_urls, source_titles = fetch_regulation_data(query, websites, api_key)
        
        # Assert that mocks were called
        mock_scrape.assert_called_once_with("https://example.com", "test_key")
        mock_extract.assert_called_once()
        
        # Assert the results
        self.assertIn("Relevant content", regulation_data)
        self.assertIn("https://example.com", source_urls)
        self.assertIn("Test Title", source_titles)
        
        # Also check the crawled content is included
        self.assertIn("Crawled content", regulation_data)
        self.assertIn("https://example.com/page", source_urls)
        self.assertIn("Page Title", source_titles)
    
    def test_extract_relevant_content(self):
        content = "This paragraph talks about emissions and safety standards.\n\nThis paragraph is about something else.\n\nHere we discuss EU regulations for electric vehicles."
        search_terms = ["emissions", "eu", "electric"]
        
        result = extract_relevant_content(content, search_terms)
        
        # Check that relevant paragraphs are included
        self.assertIn("emissions", result)
        self.assertIn("EU regulations", result)
        
        # Check that irrelevant paragraph is excluded
        self.assertNotIn("something else", result)

if __name__ == '__main__':
    unittest.main()
"""

# Create a test file for cerebras_utils
test_cerebras = """
import unittest
from unittest.mock import patch, MagicMock
from utils.cerebras_utils import (
    process_with_llama_scout,
    create_prompt,
    extract_source_indices
)

class TestCerebrasUtils(unittest.TestCase):
    
    def test_create_prompt(self):
        query = "What are the emissions standards in the EU?"
        context = "[Source 0]\\nTest content about EU emissions.\\n\\n[Source 1]\\nMore information about regulations."
        
        prompt = create_prompt(query, context)
        
        # Check that the prompt contains key elements
        self.assertIn(query, prompt)
        self.assertIn(context, prompt)
        self.assertIn("Automotive Regulatory Expert", prompt)
        self.assertIn("ONLY use information from the provided sources", prompt)
    
    def test_extract_source_indices(self):
        text = "According to [Source 0], the EU has requirements. [Source 2] also mentions standards. As [Source 0] states..."
        
        indices = extract_source_indices(text)
        
        # Check that correct indices are extracted
        self.assertEqual(set(indices), {0, 2})
        self.assertEqual(len(indices), 2)
    
    @patch('utils.cerebras_utils.CEREBRAS_SDK_AVAILABLE', False)
    @patch('utils.cerebras_utils.mock_cerebras_api')
    def test_process_with_llama_scout_mock(self, mock_api):
        mock_api.return_value = ("Test answer", [0, 1])
        
        query = "Test query"
        regulation_data = ["Data 1", "Data 2"]
        api_key = "test_key"
        
        answer, source_indices = process_with_llama_scout(query, regulation_data, api_key)
        
        # Check that mock API was called
        mock_api.assert_called_once()
        
        # Check the results
        self.assertEqual(answer, "Test answer")
        self.assertEqual(source_indices, [0, 1])
    
    def test_process_with_llama_scout_no_data(self):
        query = "Test query"
        regulation_data = []
        api_key = "test_key"
        
        with self.assertRaises(ValueError):
            process_with_llama_scout(query, regulation_data, api_key)

if __name__ == '__main__':
    unittest.main()
"""

# Create a simple test file for the MCP handler
test_mcp = """
import unittest
from unittest.mock import patch, MagicMock
from utils.mcp_handler import MCPHandler

class TestMCPHandler(unittest.TestCase):
    
    @patch('utils.mcp_handler.MCP_ENABLED', False)
    def test_mcp_disabled(self):
        # Create handler with MCP disabled
        handler = MCPHandler()
        
        # Check that MCP is disabled
        self.assertFalse(handler.enabled)
        
        # Test executing a tool locally
        result = handler.execute_tool("search_regulations", {"query": "test"})
        
        # Check that we got a result
        self.assertEqual(result["status"], "success")
        self.assertIn("regulations", result)
    
    @patch('utils.mcp_handler.subprocess.Popen')
    @patch('utils.mcp_handler.threading.Thread')
    @patch('utils.mcp_handler.MCP_ENABLED', True)
    def test_mcp_server_start(self, mock_thread, mock_popen):
        # Create mock process and thread
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        
        # Create handler with MCP enabled
        handler = MCPHandler()
        
        # Check that server process and thread were created
        self.assertEqual(handler.server_process, mock_process)
        mock_thread.assert_called_once()
    
    def test_execute_tool_locally(self):
        handler = MCPHandler()
        
        # Test search_regulations
        search_result = handler._execute_tool_locally(
            "search_regulations", 
            {"query": "test", "region": "EU", "category": "emissions"}
        )
        self.assertEqual(search_result["status"], "success")
        self.assertIn("regulations", search_result)
        self.assertEqual(search_result["regulations"][0]["region"], "EU")
        self.assertEqual(search_result["regulations"][0]["category"], "emissions")
        
        # Test get_regulation_details
        details_result = handler._execute_tool_locally(
            "get_regulation_details", 
            {"regulation_id": "EC-123", "region": "EU"}
        )
        self.assertEqual(details_result["status"], "success")
        self.assertIn("regulation", details_result)
        self.assertEqual(details_result["regulation"]["id"], "EC-123")
        
        # Test compare_regulations
        compare_result = handler._execute_tool_locally(
            "compare_regulations", 
            {"category": "emissions", "regions": ["EU", "US"]}
        )
        self.assertEqual(compare_result["status"], "success")
        self.assertIn("comparison", compare_result)
        self.assertEqual(len(compare_result["comparison"]), 2)
        
        # Test unknown tool
        unknown_result = handler._execute_tool_locally("unknown_tool", {})
        self.assertEqual(unknown_result["status"], "error")

if __name__ == '__main__':
    unittest.main()
"""

# Write the files
import os

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)

# Create utils/__init__.py
write_file('utils/__init__.py', utils_init)

# Create data/__init__.py
write_file('data/__init__.py', data_init)

# Create tests/__init__.py
write_file('tests/__init__.py', tests_init)

# Create test files
write_file('tests/test_firecrawl.py', test_firecrawl)
write_file('tests/test_cerebras.py', test_cerebras)
write_file('tests/test_mcp.py', test_mcp)

print("Initialization files created successfully.")
