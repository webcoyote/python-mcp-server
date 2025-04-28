package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func main() {
	// Parse command line arguments
	sseMode := flag.Bool("sse", false, "Enable SSE mode instead of stdio")
	flag.Parse()

	// Create an MCP server with basic capabilities
	mcpServer := server.NewMCPServer(
		"python-executor",
		"1.0.0",
	)

	// Register the Python executor
	pythonTool := mcp.NewTool(
		"execute-python",
		mcp.WithDescription("Execute Python code in an isolated environment"),
		mcp.WithString(
			"code",
			mcp.Description("Python code to execute"),
			mcp.Required(),
		),
		mcp.WithString(
			"modules",
			mcp.Description("Comma-separated list of modules to import"),
		),
	)

	mcpServer.AddTool(pythonTool, handlePythonExecution)

	// Run server in appropriate mode
	if *sseMode {
		// Create and start the SSE server
		sseServer := server.NewSSEServer(mcpServer, server.WithBaseURL("http://localhost:8080"))
		log.Printf("Starting SSE server on localhost:8080")
		if err := sseServer.Start(":8080"); err != nil {
			log.Fatalf("Failed to start SSE server: %v", err)
		}
	} else {
		// Run as stdio server
		if err := server.ServeStdio(mcpServer); err != nil {
			log.Fatalf("Failed to start stdio server: %v", err)
		}
	}
}

// Define the handler for the Python executor
func handlePythonExecution(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
	code, ok := request.Params.Arguments["code"].(string)
	if !ok {
		return mcp.NewToolResultError("Invalid code parameter"), nil
	}

	// Handle optional modules argument
	var modules []string
	if modulesStr, ok := request.Params.Arguments["modules"].(string); ok && modulesStr != "" {
		modules = strings.Split(modulesStr, ",")
	}

	tmpDir, err := os.MkdirTemp("", "python_repl")
	if err != nil {
		return mcp.NewToolResultError("Failed to create temporary directory"), nil
	}
	defer os.RemoveAll(tmpDir)

	err = os.WriteFile(path.Join(tmpDir, "script.py"), []byte(code), 0644)
	if err != nil {
		return mcp.NewToolResultError(
			fmt.Sprintf("Failed to write script to temporary file: %v", err),
		), nil
	}

	cmdArgs := []string{
		"run",
		"--rm",
		"-v",
		fmt.Sprintf("%s:/app", tmpDir),
		"mcr.microsoft.com/playwright/python:v1.49.1-noble",
	}

	shArgs := []string{}

	if len(modules) > 0 {
		shArgs = append(shArgs, "python", "-m", "pip", "install", "--quiet")
		shArgs = append(shArgs, modules...)
		shArgs = append(shArgs, "&&")
	}

	shArgs = append(shArgs, "python", path.Join("app", "script.py"))
	cmdArgs = append(cmdArgs, "sh", "-c", strings.Join(shArgs, " "))

	cmd := exec.Command("podman", cmdArgs...)
	out, err := cmd.Output()
	if err != nil {
		if exitError, ok := err.(*exec.ExitError); ok {
			return mcp.NewToolResultError(
				fmt.Sprintf("Python exited with code %d: %s",
					exitError.ExitCode(),
					string(exitError.Stderr),
				),
			), nil
		}

		return mcp.NewToolResultError(
			fmt.Sprintf("Failed to execute command: %v", err),
		), nil
	}

	return mcp.NewToolResultText(string(out)), nil

}
