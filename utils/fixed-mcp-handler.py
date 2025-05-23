import os
import json
import logging
import tempfile
import subprocess
import threading
from typing import List, Dict, Any, Optional, Callable
import time
from config import MCP_ENABLED, MCP_PORT, MCP_HOST

logger = logging.getLogger(__name__)

class MCPHandler:
    """
    Handler for Model Context Protocol (MCP) implementation.
    
    This class implements the MCP server and client capabilities,
    allowing the agent to be robust against API and model changes
    by providing a standardized protocol for accessing regulation data.
    """
    
    def __init__(self):
        """Initialize the MCP handler."""
        self.enabled = MCP_ENABLED
        self.port = MCP_PORT
        self.host = MCP_HOST
        self.server_process = None
        self.server_thread = None
        self.tools = self._initialize_tools()
        
        # Start MCP server if enabled
        if self.enabled:
            self._start_server()
    
    def _initialize_tools(self) -> List[Dict[str, Any]]:
        """
        Initialize the tools available through the MCP server.
        
        Returns:
            List of tool definitions
        """
        return [
            {
                "name": "search_regulations",
                "description": "Search for automotive regulations based on user query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "User query about automotive regulations"
                        },
                        "region": {
                            "type": "string",
                            "description": "Optional region to focus the search (e.g., EU, US, global)"
                        },
                        "category": {
                            "type": "string",
                            "description": "Optional category to focus the search (e.g., emissions, safety)"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_regulation_details",
                "description": "Get detailed information about a specific regulation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "regulation_id": {
                            "type": "string",
                            "description": "ID or name of the regulation (e.g., ECE-R100, 2018/858)"
                        },
                        "region": {
                            "type": "string",
                            "description": "Region of the regulation (e.g., EU, US, global)"
                        }
                    },
                    "required": ["regulation_id"]
                }
            },
            {
                "name": "compare_regulations",
                "description": "Compare regulations between different regions",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Category of regulations to compare (e.g., emissions, safety)"
                        },
                        "regions": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "List of regions to compare (e.g., [\"EU\", \"US\", \"China\"])"
                        }
                    },
                    "required": ["category", "regions"]
                }
            }
        ]
    
    def _start_server(self):
        """Start the MCP server in a separate thread."""
        if not self.enabled:
            logger.warning("MCP is disabled in configuration. Not starting server.")
            return
        
        try:
            # Create server script in a temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(self._generate_server_script())
                server_script_path = f.name
            
            # Start server in a separate process
            self.server_process = subprocess.Popen(
                ['python', server_script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Start monitoring thread
            self.server_thread = threading.Thread(
                target=self._monitor_server, 
                args=(self.server_process,)
            )
            self.server_thread.daemon = True
            self.server_thread.start()
            
            # Wait for server to start
            time.sleep(2)
            logger.info(f"MCP server started on {self.host}:{self.port}")
        
        except Exception as e:
            logger.error(f"Failed to start MCP server: {str(e)}")
            self.enabled = False
    
    def _generate_server_script(self) -> str:
        """
        Generate the Python script for the MCP server.
        
        Returns:
            String containing the Python code for the MCP server
        """
        # Serialize tools as a proper JSON string
        tools_json = json.dumps(self.tools, indent=2)
        
        # Create the server script with proper escaping
        server_script = f'''import os
import json
import http.server
import socketserver
import threading
import time
import uuid
from urllib.parse import urlparse, parse_qs

# MCP Server Configuration
HOST = "{self.host}"
PORT = {self.port}

# Tool definitions
TOOLS = {tools_json}

# In-memory storage for tool execution results
tool_results = {{}}

class MCPRequestHandler(http.server.BaseHTTPRequestHandler):
    def _set_headers(self, content_type="application/json"):
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_OPTIONS(self):
        self._set_headers()
        self.wfile.write(b'{{}}')
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/tools':
            # Return list of available tools
            self._set_headers()
            self.wfile.write(json.dumps({{"tools": TOOLS}}).encode('utf-8'))
        
        elif parsed_path.path.startswith('/tool-results/'):
            # Get tool execution result
            result_id = parsed_path.path.split('/')[-1]
            if result_id in tool_results:
                self._set_headers()
                self.wfile.write(json.dumps(tool_results[result_id]).encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(json.dumps({{"error": "Result not found"}}).encode('utf-8'))
        
        else:
            # Default response for unknown paths
            self._set_headers()
            self.wfile.write(json.dumps({{"status": "MCP Server Running"}}).encode('utf-8'))
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        request = json.loads(post_data)
        
        if self.path == '/execute-tool':
            # Execute a tool and return the result
            tool_name = request.get('tool_name')
            parameters = request.get('parameters', {{}})
            
            # Generate a unique ID for this execution
            result_id = str(uuid.uuid4())
            
            # Execute the tool (mock implementation)
            result = self._execute_tool(tool_name, parameters)
            
            # Store the result
            tool_results[result_id] = result
            
            # Return the result ID
            self._set_headers()
            self.wfile.write(json.dumps({{"result_id": result_id}}).encode('utf-8'))
        
        else:
            # Default response for unknown paths
            self._set_headers()
            self.wfile.write(json.dumps({{"error": "Unknown endpoint"}}).encode('utf-8'))
    
    def _execute_tool(self, tool_name, parameters):
        """Execute a tool and return the result."""
        if tool_name == "search_regulations":
            # Mock implementation of search_regulations
            query = parameters.get('query', '')
            region = parameters.get('region', 'global')
            category = parameters.get('category', '')
            
            # In a real implementation, this would search for actual regulations
            return {{
                "status": "success",
                "regulations": [
                    {{
                        "title": f"Regulation about {{category or 'automotive'}} in {{region}}",
                        "summary": f"This regulation covers {{category or 'various aspects'}} of automotive requirements in {{region}}.",
                        "region": region,
                        "category": category or "general"
                    }}
                ]
            }}
        
        elif tool_name == "get_regulation_details":
            # Mock implementation of get_regulation_details
            regulation_id = parameters.get('regulation_id', '')
            region = parameters.get('region', 'global')
            
            # In a real implementation, this would fetch actual regulation details
            return {{
                "status": "success",
                "regulation": {{
                    "id": regulation_id,
                    "title": f"{{regulation_id}} - {{region}} Regulation",
                    "description": f"Detailed description of {{regulation_id}} applicable in {{region}}.",
                    "requirements": [
                        {{
                            "text": f"Requirement 1 for {{regulation_id}}",
                            "type": "technical"
                        }},
                        {{
                            "text": f"Requirement 2 for {{regulation_id}}",
                            "type": "documentation"
                        }}
                    ]
                }}
            }}
        
        elif tool_name == "compare_regulations":
            # Mock implementation of compare_regulations
            category = parameters.get('category', '')
            regions = parameters.get('regions', [])
            
            # In a real implementation, this would compare actual regulations
            comparison = []
            for region in regions:
                comparison.append({{
                    "region": region,
                    "category": category,
                    "summary": f"{{region}} has specific requirements for {{category}}.",
                    "key_differences": f"{{region}} focuses more on X compared to other regions."
                }})
            
            return {{
                "status": "success",
                "comparison": comparison
            }}
        
        else:
            # Unknown tool
            return {{
                "status": "error",
                "message": f"Unknown tool: {{tool_name}}"
            }}

def run_server():
    handler = MCPRequestHandler
    with socketserver.TCPServer((HOST, PORT), handler) as httpd:
        print(f"MCP Server running at http://{{HOST}}:{{PORT}}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
'''
        
        return server_script
    
    def _monitor_server(self, process):
        """
        Monitor the MCP server process.
        
        Args:
            process: Server subprocess to monitor
        """
        while True:
            # Check if process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                logger.error(f"MCP server stopped unexpectedly. Return code: {process.returncode}")
                logger.error(f"Stdout: {stdout.decode('utf-8') if stdout else ''}")
                logger.error(f"Stderr: {stderr.decode('utf-8') if stderr else ''}")
                
                # Attempt to restart the server
                logger.info("Attempting to restart MCP server...")
                self._start_server()
                break
            
            # Sleep before checking again
            time.sleep(5)
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool via the MCP server.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool
        
        Returns:
            Dictionary containing the tool execution result
        """
        if not self.enabled:
            logger.warning("MCP is disabled. Executing tool locally.")
            return self._execute_tool_locally(tool_name, parameters)
        
        try:
            import requests
            
            # Send request to MCP server
            response = requests.post(
                f"http://{self.host}:{self.port}/execute-tool",
                json={
                    "tool_name": tool_name,
                    "parameters": parameters
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Error executing tool via MCP: {response.text}")
                return {"status": "error", "message": "Failed to execute tool via MCP"}
            
            result_id = response.json().get("result_id")
            
            # Get tool execution result
            result_response = requests.get(f"http://{self.host}:{self.port}/tool-results/{result_id}")
            
            if result_response.status_code != 200:
                logger.error(f"Error getting tool result via MCP: {result_response.text}")
                return {"status": "error", "message": "Failed to get tool result via MCP"}
            
            return result_response.json()
        
        except Exception as e:
            logger.error(f"Error executing tool via MCP: {str(e)}")
            logger.info("Falling back to local tool execution")
            return self._execute_tool_locally(tool_name, parameters)
    
    def _execute_tool_locally(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool locally (fallback if MCP server is unavailable).
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool
        
        Returns:
            Dictionary containing the tool execution result
        """
        # This is a simplified mock implementation - in production,
        # this would integrate with actual regulation search logic
        
        if tool_name == "search_regulations":
            query = parameters.get('query', '')
            region = parameters.get('region', 'global')
            category = parameters.get('category', '')
            
            return {
                "status": "success",
                "regulations": [
                    {
                        "title": f"Regulation about {category or 'automotive'} in {region}",
                        "summary": f"This regulation covers {category or 'various aspects'} of automotive requirements in {region}.",
                        "region": region,
                        "category": category or "general"
                    }
                ]
            }
        
        elif tool_name == "get_regulation_details":
            regulation_id = parameters.get('regulation_id', '')
            region = parameters.get('region', 'global')
            
            return {
                "status": "success",
                "regulation": {
                    "id": regulation_id,
                    "title": f"{regulation_id} - {region} Regulation",
                    "description": f"Detailed description of {regulation_id} applicable in {region}.",
                    "requirements": [
                        {
                            "text": f"Requirement 1 for {regulation_id}",
                            "type": "technical"
                        },
                        {
                            "text": f"Requirement 2 for {regulation_id}",
                            "type": "documentation"
                        }
                    ]
                }
            }
        
        elif tool_name == "compare_regulations":
            category = parameters.get('category', '')
            regions = parameters.get('regions', [])
            
            comparison = []
            for region in regions:
                comparison.append({
                    "region": region,
                    "category": category,
                    "summary": f"{region} has specific requirements for {category}.",
                    "key_differences": f"{region} focuses more on X compared to other regions."
                })
            
            return {
                "status": "success",
                "comparison": comparison
            }
        
        else:
            # Unknown tool
            return {
                "status": "error",
                "message": f"Unknown tool: {tool_name}"
            }
    
    def shutdown(self):
        """Shutdown the MCP server."""
        if self.server_process:
            logger.info("Shutting down MCP server...")
            self.server_process.terminate()
            self.server_process.wait()
            logger.info("MCP server shutdown complete")
