#!/usr/bin/env python
"""
Runner script for SAR Narrative Generator
"""
import os
import sys
import importlib.util
import argparse

# Get absolute paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, 'backend')

# Add backend directory to path
sys.path.insert(0, BACKEND_DIR)

# Import app directly - simplest solution
from app import app, config

if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='SAR Narrative Generator API')
    parser.add_argument('--host', type=str, default=getattr(config, 'API_HOST', '0.0.0.0'),
                        help='Host to run the API server on')
    parser.add_argument('--port', type=int, default=getattr(config, 'API_PORT', 8080),
                        help='Port to run the API server on')
    parser.add_argument('--debug', action='store_true', default=getattr(config, 'API_DEBUG', False),
                        help='Run in debug mode')
    
    args = parser.parse_args()
    
    print(f"Starting SAR Narrative Generator API on {args.host}:{args.port}, debug={args.debug}")
    app.run(host=args.host, port=args.port, debug=args.debug)
