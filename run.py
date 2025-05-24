#!/usr/bin/env python
"""
Convenience script to run the Hacker News MCP Server with different transport options.
"""

import argparse
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Hacker News MCP Server")
    parser.add_argument(
        "--transport", 
        type=str, 
        default=os.getenv("TRANSPORT", "sse"),
        choices=["stdio", "sse"],
        help="Transport protocol to use (stdio or sse)"
    )
    parser.add_argument(
        "--host", 
        type=str, 
        default=os.getenv("HOST", "127.0.0.1"),
        help="Host to bind to (for HTTP transports)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=int(os.getenv("PORT", "8000")),
        help="Port to bind to (for HTTP transports)"
    )
    parser.add_argument(
        "--log-level", 
        type=str, 
        default=os.getenv("LOG_LEVEL", "info"),
        choices=["debug", "info", "warning", "error", "critical"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Set log level for the root logger
    log_level = getattr(logging, args.log_level.upper())
    logging.getLogger().setLevel(log_level)
    
    print(f"Starting Hacker News MCP Server with {args.transport} transport")
    if args.transport == "sse":
        print(f"Server will be available at: http://{args.host}:{args.port}")
        print(f"SSE endpoint: http://{args.host}:{args.port}/sse")
        print(f"API documentation: http://{args.host}:{args.port}/docs")
    
    # Import and run the server's main function
    import sys
    
    # Update sys.argv with our parsed arguments to pass to the main function
    sys.argv = [sys.argv[0]]
    if args.transport:
        sys.argv.extend(["--transport", args.transport])
    if args.host:
        sys.argv.extend(["--host", args.host])
    if args.port:
        sys.argv.extend(["--port", str(args.port)])
    if args.log_level:
        sys.argv.extend(["--log-level", args.log_level])
    
    # Import and run the main function
    from app.server import main
    main()
