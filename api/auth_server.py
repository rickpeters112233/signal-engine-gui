"""
Authentication Server for MetaMask-based Login

Provides HTTP endpoints for:
- Challenge generation (nonce for signing)
- Signature verification + whitelist validation

Uses EIP-191 personal_sign for signature verification.
"""

import asyncio
import json
import logging
import secrets
import time
from typing import Dict, Optional
from aiohttp import web
from eth_account.messages import encode_defunct
from eth_account import Account

from .db import whitelist as whitelist_db

logger = logging.getLogger(__name__)

# Store active challenges with expiration (address -> {nonce, expires_at})
# Challenges expire after 5 minutes
_active_challenges: Dict[str, Dict] = {}
CHALLENGE_EXPIRY_SECONDS = 300  # 5 minutes


def generate_nonce() -> str:
    """Generate a cryptographically secure random nonce."""
    return secrets.token_hex(32)


def cleanup_expired_challenges():
    """Remove expired challenges from memory."""
    now = time.time()
    expired = [addr for addr, data in _active_challenges.items() if data['expires_at'] < now]
    for addr in expired:
        del _active_challenges[addr]


def create_sign_message(nonce: str) -> str:
    """
    Create the message that the user will sign.
    This message should be human-readable and include the nonce.
    """
    return f"Sign this message to authenticate with Gestalt Signal Engine.\n\nNonce: {nonce}"


async def handle_challenge(request: web.Request) -> web.Response:
    """
    Generate a challenge (nonce) for the given address.

    POST /auth/challenge
    Body: { "address": "0x..." }
    Response: { "message": "...", "nonce": "..." }
    """
    try:
        data = await request.json()
        address = data.get('address', '').lower()

        if not address or not address.startswith('0x') or len(address) != 42:
            return web.json_response(
                {'error': 'Invalid address format'},
                status=400
            )

        # Cleanup expired challenges periodically
        cleanup_expired_challenges()

        # Generate new challenge
        nonce = generate_nonce()
        message = create_sign_message(nonce)

        # Store challenge with expiration
        _active_challenges[address] = {
            'nonce': nonce,
            'message': message,
            'expires_at': time.time() + CHALLENGE_EXPIRY_SECONDS
        }

        logger.info(f"Generated challenge for address {address}")

        return web.json_response({
            'message': message,
            'nonce': nonce
        })

    except json.JSONDecodeError:
        return web.json_response(
            {'error': 'Invalid JSON'},
            status=400
        )
    except Exception as e:
        logger.error(f"Error generating challenge: {e}")
        return web.json_response(
            {'error': 'Internal server error'},
            status=500
        )


async def handle_verify(request: web.Request) -> web.Response:
    """
    Verify the signature and check whitelist status.

    POST /auth/verify
    Body: { "address": "0x...", "signature": "0x..." }
    Response: { "authenticated": true/false, "address": "0x...", "error": "..." }
    """
    try:
        data = await request.json()
        address = data.get('address', '').lower()
        signature = data.get('signature', '')

        if not address or not address.startswith('0x') or len(address) != 42:
            return web.json_response(
                {'authenticated': False, 'error': 'Invalid address format'},
                status=400
            )

        if not signature or not signature.startswith('0x'):
            return web.json_response(
                {'authenticated': False, 'error': 'Invalid signature format'},
                status=400
            )

        # Check if we have a valid challenge for this address
        challenge_data = _active_challenges.get(address)
        if not challenge_data:
            return web.json_response(
                {'authenticated': False, 'error': 'No active challenge for this address. Request a new challenge.'},
                status=400
            )

        # Check if challenge has expired
        if challenge_data['expires_at'] < time.time():
            del _active_challenges[address]
            return web.json_response(
                {'authenticated': False, 'error': 'Challenge expired. Request a new challenge.'},
                status=400
            )

        # Verify the signature using eth_account
        try:
            message = challenge_data['message']
            message_hash = encode_defunct(text=message)
            recovered_address = Account.recover_message(message_hash, signature=signature)
            recovered_address = recovered_address.lower()

            if recovered_address != address:
                logger.warning(f"Signature mismatch: expected {address}, got {recovered_address}")
                return web.json_response(
                    {'authenticated': False, 'error': 'Invalid signature'},
                    status=401
                )

        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return web.json_response(
                {'authenticated': False, 'error': 'Signature verification failed'},
                status=401
            )

        # Signature is valid - now check whitelist
        # Remove the used challenge first (one-time use)
        del _active_challenges[address]

        if not whitelist_db.is_whitelisted(address):
            logger.warning(f"Address {address} is not whitelisted")
            return web.json_response(
                {'authenticated': False, 'error': 'Address not whitelisted'},
                status=403
            )

        logger.info(f"Successfully authenticated address {address}")

        return web.json_response({
            'authenticated': True,
            'address': address
        })

    except json.JSONDecodeError:
        return web.json_response(
            {'authenticated': False, 'error': 'Invalid JSON'},
            status=400
        )
    except Exception as e:
        logger.error(f"Error verifying signature: {e}")
        return web.json_response(
            {'authenticated': False, 'error': 'Internal server error'},
            status=500
        )


async def handle_health(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({'status': 'ok'})


def create_app() -> web.Application:
    """Create and configure the aiohttp application."""
    app = web.Application()

    # Add CORS middleware for development
    @web.middleware
    async def cors_middleware(request: web.Request, handler):
        if request.method == 'OPTIONS':
            response = web.Response()
        else:
            response = await handler(request)

        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    app.middlewares.append(cors_middleware)

    # Add routes
    app.router.add_post('/auth/challenge', handle_challenge)
    app.router.add_post('/auth/verify', handle_verify)
    app.router.add_get('/auth/health', handle_health)
    app.router.add_options('/auth/challenge', lambda r: web.Response())
    app.router.add_options('/auth/verify', lambda r: web.Response())

    return app


class AuthServer:
    """Authentication server manager."""

    def __init__(self, host: str = "localhost", port: int = 8766):
        self.host = host
        self.port = port
        self.app = create_app()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.is_running = False

        logger.info(f"AuthServer initialized on {host}:{port}")

    async def start(self):
        """Start the authentication server."""
        logger.info(f"Starting Auth server on http://{self.host}:{self.port}")

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()

        self.is_running = True
        logger.info("Auth server started successfully")

    async def stop(self):
        """Stop the authentication server."""
        logger.info("Stopping Auth server...")

        if self.runner:
            await self.runner.cleanup()

        self.is_running = False
        logger.info("Auth server stopped")

    async def run_forever(self):
        """Run the server indefinitely."""
        await self.start()
        try:
            await asyncio.Future()  # Run forever
        except asyncio.CancelledError:
            await self.stop()


# Singleton instance
_auth_server_instance: Optional[AuthServer] = None


def get_auth_server(host: str = "localhost", port: int = 8766) -> AuthServer:
    """Get or create the singleton AuthServer instance."""
    global _auth_server_instance

    if _auth_server_instance is None:
        _auth_server_instance = AuthServer(host=host, port=port)

    return _auth_server_instance
