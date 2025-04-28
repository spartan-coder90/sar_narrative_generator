"""
Main entry point for SAR Narrative Generator API
"""
from flask import Flask, jsonify
import os
import sys
import argparse

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Now use imports relative to the backend directory
from api.routes import api_bp
import config  # import directly since we're in the same directory
from utils.logger import get_logger

logger = get_logger(__name__)

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    
    # Register blueprints
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'status': 'error',
            'message': 'Route not found'
        }), 404
    
    @app.errorhandler(500)
    def server_error(error):
        logger.error(f"Internal server error: {str(error)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500
    
    return app

def main():
    """Main function to run the application"""
    parser = argparse.ArgumentParser(description='SAR Narrative Generator API')
    parser.add_argument('--host', type=str, default=config.API_HOST,
                        help='Host to run the API server on')
    parser.add_argument('--port', type=int, default=config.API_PORT,
                        help='Port to run the API server on')
    parser.add_argument('--debug', action='store_true', default=config.API_DEBUG,
                        help='Run in debug mode')
    
    args = parser.parse_args()
    
    app = create_app()
    logger.info(f"Starting SAR Narrative Generator API on {args.host}:{args.port}, debug={args.debug}")
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == '__main__':
    main()