"""
SSH Cluster Connector Service
Handles SSH connections to retrieve kubeconfig from remote clusters

Copyright (C) 2026 K8s Orchestrator Contributors
Licensed under GPL-3.0
"""
import asyncio
import asyncssh
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class SSHClusterConnector:
    """Manages SSH connections to retrieve kubeconfig from remote clusters"""

    DEFAULT_KUBECONFIG_PATHS = {
        'k3s': '/etc/rancher/k3s/k3s.yaml',
        'standard': '~/.kube/config',
        'root': '/root/.kube/config'
    }

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        private_key: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize SSH connector

        Args:
            host: SSH hostname or IP
            port: SSH port
            username: SSH username
            private_key: SSH private key content (for key auth)
            password: SSH password (for password auth or key passphrase)
        """
        self.host = host
        self.port = port
        self.username = username
        self.private_key = private_key
        self.password = password

        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """Validate that we have either private key or password"""
        if not self.private_key and not self.password:
            raise ValueError('Either private_key or password must be provided')

    def connect_and_retrieve_kubeconfig(
        self,
        kubeconfig_path: str = '/etc/rancher/k3s/k3s.yaml'
    ) -> Dict:
        """
        Connect to server via SSH and retrieve kubeconfig

        Args:
            kubeconfig_path: Path to kubeconfig file on remote server

        Returns:
            dict with 'success', 'kubeconfig', and optional 'error' keys
        """
        return asyncio.run(self._async_connect_and_retrieve(kubeconfig_path))

    async def _async_connect_and_retrieve(self, kubeconfig_path: str) -> Dict:
        """Async implementation of connect and retrieve"""
        # Step 1: Establish SSH connection
        connection_result = await self._establish_connection()
        if not connection_result['success']:
            return connection_result

        conn = connection_result['connection']

        try:
            # Step 2: Retrieve kubeconfig
            kubeconfig_result = await self._retrieve_kubeconfig(conn, kubeconfig_path)

            if not kubeconfig_result['success']:
                return kubeconfig_result

            # Step 3: Process kubeconfig (replace localhost with actual host)
            processed_kubeconfig = self._process_kubeconfig(
                kubeconfig_result['kubeconfig']
            )

            return {
                'success': True,
                'kubeconfig': processed_kubeconfig
            }

        finally:
            await conn.close()

    async def _establish_connection(self) -> Dict:
        """
        Establish SSH connection to remote server

        Returns:
            dict with 'success', 'connection', and optional 'error'
        """
        try:
            # Prepare authentication
            client_keys = None
            if self.private_key:
                try:
                    client_key = asyncssh.import_private_key(
                        self.private_key,
                        passphrase=self.password
                    )
                    client_keys = [client_key]
                except Exception as e:
                    logger.error(f"Failed to import private key: {e}")
                    return {
                        'success': False,
                        'error': f'Invalid private key: {str(e)}'
                    }

            # Establish connection
            conn = await asyncssh.connect(
                self.host,
                port=self.port,
                username=self.username,
                client_keys=client_keys,
                password=self.password if not client_keys else None,
                known_hosts=None,  # Disable host key checking
                connect_timeout=30
            )

            logger.info(f"SSH connection established to {self.username}@{self.host}:{self.port}")

            return {
                'success': True,
                'connection': conn
            }

        except asyncssh.PermissionDenied:
            return {
                'success': False,
                'error': 'Authentication failed. Check your credentials.'
            }
        except asyncssh.ConnectionLost:
            return {
                'success': False,
                'error': f'Connection lost to {self.host}:{self.port}'
            }
        except OSError as e:
            return {
                'success': False,
                'error': f'Network error: {str(e)}'
            }
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            return {
                'success': False,
                'error': f'SSH connection failed: {str(e)}'
            }

    async def _retrieve_kubeconfig(
        self,
        conn: asyncssh.SSHClientConnection,
        kubeconfig_path: str
    ) -> Dict:
        """
        Retrieve kubeconfig from remote server

        Args:
            conn: Active SSH connection
            kubeconfig_path: Path to kubeconfig on server

        Returns:
            dict with 'success', 'kubeconfig', and optional 'error'
        """
        try:
            # Expand tilde in path
            if kubeconfig_path.startswith('~'):
                expand_result = await conn.run(f'echo {kubeconfig_path}')
                if expand_result.exit_status == 0:
                    kubeconfig_path = expand_result.stdout.strip()

            # Try to read kubeconfig with sudo
            result = await conn.run(f'sudo cat {kubeconfig_path}')

            if result.exit_status != 0:
                # Try without sudo
                result = await conn.run(f'cat {kubeconfig_path}')

            if result.exit_status != 0:
                return {
                    'success': False,
                    'error': f'Cannot read kubeconfig at {kubeconfig_path}. '
                             f'Check path and permissions.'
                }

            kubeconfig_content = result.stdout

            if not kubeconfig_content or len(kubeconfig_content) < 50:
                return {
                    'success': False,
                    'error': f'Kubeconfig at {kubeconfig_path} is empty or invalid'
                }

            logger.info(f"Retrieved kubeconfig from {kubeconfig_path}")

            return {
                'success': True,
                'kubeconfig': kubeconfig_content
            }

        except Exception as e:
            logger.error(f"Failed to retrieve kubeconfig: {e}")
            return {
                'success': False,
                'error': f'Failed to retrieve kubeconfig: {str(e)}'
            }

    def _process_kubeconfig(self, kubeconfig: str) -> str:
        """
        Process kubeconfig to replace localhost with actual host IP

        Args:
            kubeconfig: Raw kubeconfig content

        Returns:
            Processed kubeconfig
        """
        # Replace common localhost references
        processed = kubeconfig

        replacements = [
            ('server: https://127.0.0.1:6443', f'server: https://{self.host}:6443'),
            ('server: https://localhost:6443', f'server: https://{self.host}:6443'),
            ('server: https://0.0.0.0:6443', f'server: https://{self.host}:6443'),
        ]

        for old, new in replacements:
            processed = processed.replace(old, new)

        return processed

    @staticmethod
    def validate_kubeconfig_path(path: str) -> bool:
        """
        Validate kubeconfig path format

        Args:
            path: Path to validate

        Returns:
            True if valid
        """
        if not path:
            return False

        # Basic validation - must be absolute or tilde path
        if not (path.startswith('/') or path.startswith('~')):
            return False

        # Check for dangerous characters
        dangerous_chars = [';', '&', '|', '$', '`']
        if any(char in path for char in dangerous_chars):
            return False

        return True
