#!/usr/bin/env python3
"""Test script for executing Python code via MCP server"""

import json
import subprocess
import threading
import queue
import time
import argparse
import sys

class PythonMCPTester:
    def __init__(self, pretty=False):
        self.process = None
        self.output_queue = queue.Queue()
        self.reader_thread = None
        self.pretty = pretty
        self.initialized = False
        self.request_id = 0
        
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
                
    def clear_queue(self):
        """Clear any pending messages in the output queue"""
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except queue.Empty:
                break

    def send_request(self, request):
        """Send a JSON-RPC request to the server"""
        # Clear any pending responses before sending new request
        self.clear_queue()

        request_str = json.dumps(request)
        if self.pretty:
            print("\n→ Request:")
            print("  " + json.dumps(request, indent=2).replace("\n", "\n  "))
        else:
            print(f"\n→ {request_str}")
        self.process.stdin.write(request_str + '\n')
        self.process.stdin.flush()
        
    def get_response(self, timeout=10):
        """Get response from server with timeout"""
        try:
            response = self.output_queue.get(timeout=timeout)
            if self.pretty:
                try:
                    response_obj = json.loads(response)
                    print("\n← Response:")
                    print("  " + json.dumps(response_obj, indent=2).replace("\n", "\n  "))
                    return response_obj
                except json.JSONDecodeError:
                    print(f"\n← {response}")
                    return response
            else:
                print(f"\n← {response}")
                try:
                    return json.loads(response)
                except:
                    return response
        except queue.Empty:
            print(f"\n← (no response within {timeout}s)")
            return None
            
    def initialize(self):
        """Initialize the MCP connection"""
        if self.initialized:
            return True
            
        print("\n=== Initializing MCP Server ===")
        
        # Send initialize request
        self.request_id += 1
        self.send_request({
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "clientInfo": {
                    "name": "python-exec-tester",
                    "version": "1.0.0"
                }
            }
        })
        
        response = self.get_response()
        if not response:
            print("Failed to initialize server")
            return False
            
        # Send initialized notification
        self.send_request({
            "jsonrpc": "2.0",
            "method": "initialized"
        })
        time.sleep(0.5)
        
        self.initialized = True
        return True
        
    def execute_python(self, code, modules=None):
        """Execute Python code through the MCP server"""
        if not self.initialized:
            if not self.initialize():
                return None
                
        print(f"\n=== Executing Python Code ===")
        if modules:
            print(f"Modules to install: {modules}")
        print(f"Code:\n{code}\n")
        
        # Increment request ID for each call
        self.request_id += 1

        params = {
            "name": "execute-python",
            "arguments": {
                "code": code
            }
        }
        
        if modules:
            params["arguments"]["modules"] = modules
            
        self.send_request({
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/call",
            "params": params
        })
        
        response = self.get_response(timeout=30)  # Longer timeout for code execution
        
        if response and isinstance(response, dict):
            if "result" in response:
                result = response["result"]
                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        text_content = content[0].get("text", "")
                        print("\n=== Execution Result ===")
                        print(text_content)
                        # Wait a bit to ensure output is complete
                        time.sleep(0.5)
                        return text_content
                        
        return response
        
    def run_examples(self):
        """Run example Python code executions"""
        self.start_server()
        
        # Initialize once at the beginning
        if not self.initialize():
            print("Failed to initialize server")
            return

        # Example 1: Simple calculation
        print("\n" + "="*60)
        print("Example 1: Simple Calculation")
        print("="*60)
        self.execute_python("""
# Calculate factorial
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n-1)

result = factorial(5)
print(f"Factorial of 5 is: {result}")

# Calculate fibonacci
def fibonacci(n):
    a, b = 0, 1
    fib_sequence = []
    for _ in range(n):
        fib_sequence.append(a)
        a, b = b, a + b
    return fib_sequence

print(f"First 10 Fibonacci numbers: {fibonacci(10)}")
""")
        
        # Wait between tests to avoid interleaving
        time.sleep(1)

        # Example 2: Working with data structures
        print("\n" + "="*60)
        print("Example 2: Data Processing")
        print("="*60)
        self.execute_python("""
import json
import statistics

# Create sample data
data = {
    "numbers": [23, 45, 67, 89, 12, 34, 56, 78, 90, 21],
    "names": ["Alice", "Bob", "Charlie", "Diana", "Eve"]
}

# Process numbers
mean = statistics.mean(data["numbers"])
median = statistics.median(data["numbers"])
stdev = statistics.stdev(data["numbers"])

print(f"Statistics for numbers:")
print(f"  Mean: {mean:.2f}")
print(f"  Median: {median}")
print(f"  Std Dev: {stdev:.2f}")

# Process names
sorted_names = sorted(data["names"])
name_lengths = {name: len(name) for name in data["names"]}

print(f"\\nName analysis:")
print(f"  Sorted: {sorted_names}")
print(f"  Lengths: {json.dumps(name_lengths, indent=2)}")
""")
        
        # Wait between tests to avoid interleaving
        time.sleep(1)

        # Example 3: Using external modules
        print("\n" + "="*60)
        print("Example 3: Using External Modules (pandas)")
        print("="*60)
        self.execute_python("""
import pandas as pd
import numpy as np

# Create a simple DataFrame
df = pd.DataFrame({
    'A': np.random.randn(5),
    'B': np.random.randn(5),
    'C': np.random.randn(5)
})

print("DataFrame:")
print(df)
print(f"\\nDataFrame shape: {df.shape}")
print(f"\\nColumn means:")
print(df.mean())
print(f"\\nDataFrame info:")
df.info()
""", modules="pandas,numpy")
        
        # Wait between tests to avoid interleaving
        time.sleep(1)

        # Example 4: Error handling
        print("\n" + "="*60)
        print("Example 4: Error Handling")
        print("="*60)
        self.execute_python("""
# This will cause an error
try:
    result = 10 / 0
except ZeroDivisionError as e:
    print(f"Caught error: {e}")
    
# Undefined variable error (will not be caught)
print(undefined_variable)
""")
        
    def run_interactive(self):
        """Run in interactive mode"""
        self.start_server()
        
        if not self.initialize():
            print("Failed to initialize server")
            return
            
        print("\n=== Interactive Python Execution Mode ===")
        print("Enter Python code (use 'EOF' on a single line to execute)")
        print("Use 'MODULES: module1,module2' to specify modules to install")
        print("Type 'EXIT' to quit\n")
        
        while True:
            modules = None
            code_lines = []
            
            print("\n>>> Enter code (EOF to execute, EXIT to quit):")
            
            while True:
                try:
                    line = input()
                    
                    if line == "EXIT":
                        return
                    elif line == "EOF":
                        break
                    elif line.startswith("MODULES:"):
                        modules = line[8:].strip()
                    else:
                        code_lines.append(line)
                except EOFError:
                    break
                    
            if code_lines:
                code = "\n".join(code_lines)
                self.execute_python(code, modules)
                
    def cleanup(self):
        """Clean up and shutdown"""
        if self.initialized:
            print("\n=== Shutting down ===")
            self.request_id += 1
            self.send_request({
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "shutdown",
                "params": {}
            })
            time.sleep(0.5)
            
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Python code execution via MCP server")
    parser.add_argument('-p', '--pretty', action='store_true', 
                        help='Pretty-print JSON requests and responses')
    parser.add_argument('-i', '--interactive', action='store_true',
                        help='Run in interactive mode')
    parser.add_argument('-c', '--code', type=str,
                        help='Execute specific Python code')
    parser.add_argument('-m', '--modules', type=str,
                        help='Comma-separated list of modules to install')
    args = parser.parse_args()
    
    tester = PythonMCPTester(pretty=args.pretty)
    
    try:
        if args.code:
            # Execute specific code
            tester.start_server()
            tester.execute_python(args.code, args.modules)
        elif args.interactive:
            # Interactive mode
            tester.run_interactive()
        else:
            # Run examples
            tester.run_examples()
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        tester.cleanup()
        print("\nTest completed!")
