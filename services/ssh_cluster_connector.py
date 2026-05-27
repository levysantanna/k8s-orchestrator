"""
SSH Cluster Connector Service
Handles SSH connections to retrieve kubeconfig from remote clusters

Copyright (C) 2026 K8s Orchestrator Contributors
Licensed under GPL-3.0
"""
import paramiko
from typing import Optional, Dict
import logging
import io
from services.connection_monitor import connection_monitor

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
        # Log connection attempt
        connection_monitor.log_event(
            event_type='connect',
            connection_type='ssh',
            host=self.host,
            username=self.username,
            message=f'Attempting SSH connection (port {self.port})',
            status='info'
        )

        ssh_client = None

        try:
            # Step 1: Establish SSH connection
            connection_result = self._establish_connection()
            if not connection_result['success']:
                return connection_result

            ssh_client = connection_result['connection']

            # Step 2: Retrieve kubeconfig
            kubeconfig_result = self._retrieve_kubeconfig(ssh_client, kubeconfig_path)

            if not kubeconfig_result['success']:
                return kubeconfig_result

            # Step 3: Process kubeconfig (replace localhost with actual host)
            processed_kubeconfig = self._process_kubeconfig(
                kubeconfig_result['kubeconfig']
            )

            # Log success
            connection_monitor.log_event(
                event_type='info',
                connection_type='ssh',
                host=self.host,
                username=self.username,
                message=f'Kubeconfig retrieved successfully from {kubeconfig_path}',
                status='success'
            )

            return {
                'success': True,
                'kubeconfig': processed_kubeconfig
            }

        except Exception as e:
            # Log error
            connection_monitor.log_event(
                event_type='error',
                connection_type='ssh',
                host=self.host,
                username=self.username,
                message=f'Failed to retrieve kubeconfig: {str(e)}',
                status='error'
            )
            raise

        finally:
            if ssh_client:
                ssh_client.close()
                logger.info(f"SSH connection closed to {self.host}")

                # Log disconnect
                connection_monitor.log_event(
                    event_type='disconnect',
                    connection_type='ssh',
                    host=self.host,
                    username=self.username,
                    message='SSH connection closed',
                    status='info'
                )

    def _establish_connection(self) -> Dict:
        """
        Establish SSH connection to remote server

        Returns:
            dict with 'success', 'connection', and optional 'error'
        """
        try:
            # Create SSH client
            ssh_client = paramiko.SSHClient()

            # Auto-add unknown hosts (similar to known_hosts=None in asyncssh)
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Prepare authentication
            connect_kwargs = {
                'hostname': self.host,
                'port': self.port,
                'username': self.username,
                'timeout': 30,
                'banner_timeout': 30,
                'auth_timeout': 30
            }

            # Try key-based authentication first
            if self.private_key:
                try:
                    # Convert string private key to file-like object
                    key_file = io.StringIO(self.private_key)

                    # Try different key types (DSS/DSA deprecated in paramiko 5.0+)
                    pkey = None
                    key_types = [
                        ('RSA', paramiko.RSAKey),
                        ('Ed25519', paramiko.Ed25519Key),
                        ('ECDSA', paramiko.ECDSAKey)
                    ]

                    last_error = None
                    for key_name, key_type in key_types:
                        try:
                            key_file.seek(0)
                            pkey = key_type.from_private_key(
                                key_file,
                                password=self.password
                            )
                            logger.info(f"Successfully loaded {key_name} private key")
                            break
                        except paramiko.ssh_exception.SSHException as e:
                            # Wrong key type, try next
                            last_error = e
                            continue
                        except paramiko.ssh_exception.PasswordRequiredException:
                            # Key requires passphrase but none provided
                            last_error = "Private key is encrypted but no passphrase provided"
                            break
                        except Exception as e:
                            last_error = e
                            continue

                    if not pkey:
                        error_msg = str(last_error) if last_error else "Unknown key format"
                        logger.error(f"Failed to import private key: {error_msg}")

                        # Provide helpful error message
                        if "passphrase" in error_msg.lower():
                            friendly_error = "Private key is encrypted. Please provide the passphrase in the password field."
                        elif "not a valid" in error_msg.lower():
                            friendly_error = "Invalid private key format. Supported: RSA, Ed25519, ECDSA (DSA/DSS deprecated)"
                        else:
                            friendly_error = f"Cannot load private key: {error_msg}"

                        return {
                            'success': False,
                            'error': friendly_error
                        }

                    connect_kwargs['pkey'] = pkey
                    logger.info(f"Using private key authentication for {self.username}@{self.host}")

                except Exception as e:
                    logger.error(f"Failed to load private key: {e}")
                    return {
                        'success': False,
                        'error': f'Error loading private key: {str(e)}'
                    }

            # Add password if provided (used for password auth or key passphrase)
            if self.password and not self.private_key:
                connect_kwargs['password'] = self.password
                logger.info(f"Using password authentication for {self.username}@{self.host}")

            # Establish connection
            ssh_client.connect(**connect_kwargs)

            logger.info(f"SSH connection established to {self.username}@{self.host}:{self.port}")

            # Log successful connection
            connection_monitor.log_event(
                event_type='connect',
                connection_type='ssh',
                host=self.host,
                username=self.username,
                message='SSH connection established successfully',
                status='success'
            )

            return {
                'success': True,
                'connection': ssh_client
            }

        except paramiko.AuthenticationException as e:
            logger.error(f"Authentication failed: {e}")
            connection_monitor.log_event(
                event_type='error',
                connection_type='ssh',
                host=self.host,
                username=self.username,
                message='Authentication failed - check credentials',
                status='error'
            )
            return {
                'success': False,
                'error': 'Authentication failed. Check your credentials.'
            }
        except paramiko.SSHException as e:
            logger.error(f"SSH error: {e}")
            connection_monitor.log_event(
                event_type='error',
                connection_type='ssh',
                host=self.host,
                username=self.username,
                message=f'SSH error: {str(e)}',
                status='error'
            )
            return {
                'success': False,
                'error': f'SSH connection error: {str(e)}'
            }
        except OSError as e:
            logger.error(f"Network error: {e}")
            connection_monitor.log_event(
                event_type='error',
                connection_type='ssh',
                host=self.host,
                username=self.username,
                message=f'Network error: Cannot reach {self.host}:{self.port}',
                status='error'
            )
            return {
                'success': False,
                'error': f'Network error: Cannot reach {self.host}:{self.port} - {str(e)}'
            }
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            connection_monitor.log_event(
                event_type='error',
                connection_type='ssh',
                host=self.host,
                username=self.username,
                message=f'Connection failed: {str(e)}',
                status='error'
            )
            return {
                'success': False,
                'error': f'SSH connection failed: {str(e)}'
            }

    def _retrieve_kubeconfig(
        self,
        ssh_client: paramiko.SSHClient,
        kubeconfig_path: str
    ) -> Dict:
        """
        Retrieve kubeconfig from remote server

        Args:
            ssh_client: Active SSH connection
            kubeconfig_path: Path to kubeconfig on server

        Returns:
            dict with 'success', 'kubeconfig', and optional 'error'
        """
        try:
            # Expand tilde in path
            if kubeconfig_path.startswith('~'):
                stdin, stdout, stderr = ssh_client.exec_command(f'echo {kubeconfig_path}')
                expanded_path = stdout.read().decode('utf-8').strip()
                if expanded_path:
                    kubeconfig_path = expanded_path

            logger.info(f"Attempting to read kubeconfig from {kubeconfig_path}")

            # Try to read kubeconfig with sudo
            stdin, stdout, stderr = ssh_client.exec_command(f'sudo cat {kubeconfig_path}')
            exit_status = stdout.channel.recv_exit_status()

            if exit_status != 0:
                # Try without sudo
                logger.info("Sudo failed, trying without sudo")
                stdin, stdout, stderr = ssh_client.exec_command(f'cat {kubeconfig_path}')
                exit_status = stdout.channel.recv_exit_status()

            if exit_status != 0:
                error_msg = stderr.read().decode('utf-8').strip()
                logger.error(f"Failed to read kubeconfig: {error_msg}")
                return {
                    'success': False,
                    'error': f'Cannot read kubeconfig at {kubeconfig_path}. '
                             f'Check path and permissions. Error: {error_msg}'
                }

            kubeconfig_content = stdout.read().decode('utf-8')

            if not kubeconfig_content or len(kubeconfig_content) < 50:
                return {
                    'success': False,
                    'error': f'Kubeconfig at {kubeconfig_path} is empty or invalid'
                }

            logger.info(f"Successfully retrieved kubeconfig from {kubeconfig_path} ({len(kubeconfig_content)} bytes)")

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
            if old in processed:
                processed = processed.replace(old, new)
                logger.info(f"Replaced '{old}' with '{new}' in kubeconfig")

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
