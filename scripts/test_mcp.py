#!/usr/bin/env python3
"""Test script for python-mcp-server stdio communication"""

import json
import subprocess
import threading
import queue
import time
import argparse

class MCPServerTester:
    def __init__(self, pretty=False):
        self.process = None
        self.output_queue = queue.Queue()
        self.reader_thread = None
        self.pretty = pretty
        
    def start_server(self):
        """Start the MCP server process"""
        print("Starting python-mcp-server...")
        self.process = subprocess.Popen(
            ['python-mcp-server'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=0
        )
        
        # Start reader thread
        self.reader_thread = threading.Thread(target=self._read_output)
        self.reader_thread.daemon = True
        self.reader_thread.start()
        
        # Give server time to start
        time.sleep(0.5)
        
    def _read_output(self):
        """Read output from server in background thread"""
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if line:
                    self.output_queue.put(line.strip())
            except:
                break
                
    def send_request(self, request):
        """Send a JSON-RPC request to the server"""
        request_str = json.dumps(request)
        if self.pretty:
            print("  → Request:")
            print("    " + json.dumps(request, indent=2).replace("\n", "\n    "))
        else:
            print(f"  → {request_str}")
        self.process.stdin.write(request_str + '\n')
        self.process.stdin.flush()
        
    def get_response(self, timeout=2):
        """Get response from server with timeout"""
        try:
            response = self.output_queue.get(timeout=timeout)
            if self.pretty:
                try:
                    response_obj = json.loads(response)
                    print("  ← Response:")
                    print("    " + json.dumps(response_obj, indent=2).replace("\n", "\n    "))
                except json.JSONDecodeError:
                    print(f"  ← {response}")
            else:
                print(f"  ← {response}")
            return response
        except queue.Empty:
            print(f"  ← (no response within {timeout}s)")
            return None
            
    def run_tests(self):
        """Run test sequence"""
        print("\n=== MCP Server Test ===\n")
        
        self.start_server()
        
        # Test 1: Initialize
        print("Test 1: Initialize")
        self.send_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        })
        self.get_response()
        
        # Send initialized notification
        print("\nSending initialized notification")
        self.send_request({
            "jsonrpc": "2.0",
            "method": "initialized"
        })
        time.sleep(0.5)  # Give time to process
        
        # Test 2: List tools
        print("\nTest 2: List Tools")
        self.send_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        self.get_response()
        
        # Test 3: List prompts
        print("\nTest 3: List Prompts")
        self.send_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "prompts/list",
            "params": {}
        })
        self.get_response()
        
        # Test 4: List resources
        print("\nTest 4: List Resources")
        self.send_request({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/list",
            "params": {}
        })
        self.get_response()
        
        # Clean up
        print("\nShutting down...")
        self.send_request({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "shutdown",
            "params": {}
        })
        time.sleep(0.5)
        
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=2)
            
        print("\nTests completed!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test MCP server stdio communication")
    parser.add_argument('-p', '--pretty', action='store_true', 
                        help='Pretty-print JSON requests and responses')
    args = parser.parse_args()
    
    tester = MCPServerTester(pretty=args.pretty)
    try:
        tester.run_tests()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        if tester.process:
            tester.process.terminate()
    except Exception as e:
        print(f"\nError: {e}")
        if tester.process:
            tester.process.terminate()
