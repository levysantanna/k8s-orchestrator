"""
K3s Remote Deployment Service
Deploy k3s to remote servers via SSH

Copyright (C) 2026 K8s Orchestrator Contributors
Licensed under GPL-3.0
"""
from typing import Dict, Optional, List
import asyncio
import asyncssh
import base64
from datetime import datetime
from functions.base import get_db_session
from models.cluster import Cluster, ClusterConnectionType, ClusterStatus
from services.cluster_service import ClusterService

class K3sDeploymentService:
    """Service for deploying k3s to remote servers via SSH"""

    @staticmethod
    async def deploy_k3s_server(
        cluster_name: str,
        ssh_host: str,
        ssh_port: int,
        ssh_username: str,
        ssh_private_key: str,
        ssh_password: Optional[str] = None,
        k3s_version: str = 'stable',
        k3s_options: Optional[Dict] = None
    ) -> Dict:
        """
        Deploy k3s server (control plane) to remote host

        Args:
            cluster_name: Name for the new cluster
            ssh_host: SSH hostname or IP
            ssh_port: SSH port (usually 22 or 2222)
            ssh_username: SSH username
            ssh_private_key: SSH private key content
            ssh_password: SSH password (if key has passphrase)
            k3s_version: K3s version (stable, latest, or v1.28.5)
            k3s_options: Additional k3s install options

        Returns:
            dict: Deployment result with kubeconfig and cluster info
        """
        try:
            # Connect to remote server via SSH
            connection_result = await K3sDeploymentService._connect_ssh(
                ssh_host, ssh_port, ssh_username, ssh_private_key, ssh_password
            )

            if not connection_result['success']:
                return connection_result

            conn = connection_result['connection']

            # Check prerequisites
            prereq_check = await K3sDeploymentService._check_prerequisites(conn)
            if not prereq_check['success']:
                await conn.close()
                return prereq_check

            # Install k3s
            install_result = await K3sDeploymentService._install_k3s_server(
                conn, k3s_version, k3s_options
            )

            if not install_result['success']:
                await conn.close()
                return install_result

            # Wait for k3s to be ready
            ready_result = await K3sDeploymentService._wait_for_k3s_ready(conn)
            if not ready_result['success']:
                await conn.close()
                return ready_result

            # Retrieve kubeconfig
            kubeconfig_result = await K3sDeploymentService._get_kubeconfig(conn, ssh_host)
            if not kubeconfig_result['success']:
                await conn.close()
                return kubeconfig_result

            # Get k3s token for joining nodes
            token_result = await K3sDeploymentService._get_k3s_token(conn)

            # Close SSH connection
            await conn.close()

            # Save cluster to database
            kubeconfig_b64 = base64.b64encode(
                kubeconfig_result['kubeconfig'].encode('utf-8')
            ).decode('utf-8')

            cluster = ClusterService.add_cluster(
                name=cluster_name,
                api_server_url=f"https://{ssh_host}:6443",
                kubeconfig_content=kubeconfig_b64,
                description=f"k3s {k3s_version} deployed via orchestrator",
                ssh_config={
                    'host': ssh_host,
                    'port': ssh_port,
                    'username': ssh_username,
                    'key_content': ssh_private_key
                }
            )

            return {
                'success': True,
                'message': f'k3s server deployed successfully on {ssh_host}',
                'cluster_id': cluster.id,
                'cluster_name': cluster.name,
                'api_server': f"https://{ssh_host}:6443",
                'k3s_version': install_result.get('version'),
                'k3s_token': token_result.get('token'),
                'kubeconfig': kubeconfig_result['kubeconfig'],
                'instructions': [
                    'k3s server is running',
                    'Cluster has been added to orchestrator',
                    f'API Server: https://{ssh_host}:6443',
                    'To add worker nodes, use the k3s_token provided',
                    f'Worker join command: curl -sfL https://get.k3s.io | K3S_URL=https://{ssh_host}:6443 K3S_TOKEN={token_result.get("token", "SEE_SERVER")} sh -'
                ]
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Deployment failed: {str(e)}'
            }

    @staticmethod
    async def _connect_ssh(
        host: str,
        port: int,
        username: str,
        private_key: str,
        password: Optional[str] = None
    ) -> Dict:
        """
        Establish SSH connection to remote server

        Args:
            host: SSH hostname
            port: SSH port
            username: SSH username
            private_key: SSH private key content
            password: Optional password

        Returns:
            dict: Connection result with connection object
        """
        try:
            # Create SSH client key from string
            client_key = asyncssh.import_private_key(private_key, passphrase=password)

            # Connect to remote server
            conn = await asyncssh.connect(
                host,
                port=port,
                username=username,
                client_keys=[client_key],
                known_hosts=None,  # Disable host key checking (use with caution)
                connect_timeout=30
            )

            return {
                'success': True,
                'connection': conn
            }

        except asyncssh.PermissionDenied:
            return {
                'success': False,
                'error': 'SSH authentication failed. Check credentials.'
            }
        except asyncssh.ConnectionLost:
            return {
                'success': False,
                'error': f'SSH connection to {host}:{port} failed. Check host is reachable.'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'SSH connection error: {str(e)}'
            }

    @staticmethod
    async def _check_prerequisites(conn: asyncssh.SSHClientConnection) -> Dict:
        """
        Check if server meets k3s requirements

        Args:
            conn: SSH connection

        Returns:
            dict: Check result
        """
        try:
            # Check if running as root or has sudo
            result = await conn.run('id -u', check=False)
            if result.exit_status != 0:
                return {'success': False, 'error': 'Cannot determine user privileges'}

            uid = result.stdout.strip()
            if uid != '0':
                # Check if user has sudo
                sudo_check = await conn.run('sudo -n true', check=False)
                if sudo_check.exit_status != 0:
                    return {
                        'success': False,
                        'error': 'User must be root or have passwordless sudo access'
                    }

            # Check if k3s is already installed
            k3s_check = await conn.run('which k3s', check=False)
            if k3s_check.exit_status == 0:
                return {
                    'success': False,
                    'error': 'k3s is already installed on this server'
                }

            # Check if port 6443 is available
            port_check = await conn.run('ss -tuln | grep :6443', check=False)
            if port_check.exit_status == 0:
                return {
                    'success': False,
                    'error': 'Port 6443 is already in use'
                }

            return {'success': True}

        except Exception as e:
            return {
                'success': False,
                'error': f'Prerequisites check failed: {str(e)}'
            }

    @staticmethod
    async def _install_k3s_server(
        conn: asyncssh.SSHClientConnection,
        version: str = 'stable',
        options: Optional[Dict] = None
    ) -> Dict:
        """
        Install k3s server on remote host

        Args:
            conn: SSH connection
            version: K3s version
            options: Additional install options

        Returns:
            dict: Installation result
        """
        try:
            # Build install command
            install_env = []

            if version and version != 'stable':
                install_env.append(f'INSTALL_K3S_VERSION={version}')

            if options:
                for key, value in options.items():
                    install_env.append(f'{key}={value}')

            env_string = ' '.join(install_env)
            install_cmd = f'{env_string} curl -sfL https://get.k3s.io | sh -'

            # Add sudo if needed
            uid_result = await conn.run('id -u')
            if uid_result.stdout.strip() != '0':
                install_cmd = f'sudo {install_cmd}'

            # Run installation
            result = await conn.run(install_cmd, timeout=300)  # 5 minute timeout

            if result.exit_status != 0:
                return {
                    'success': False,
                    'error': f'k3s installation failed: {result.stderr}'
                }

            # Get installed version
            version_result = await conn.run('k3s --version | head -1')
            version_output = version_result.stdout.strip()

            return {
                'success': True,
                'message': 'k3s installed successfully',
                'version': version_output
            }

        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': 'k3s installation timed out (>5 minutes)'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Installation error: {str(e)}'
            }

    @staticmethod
    async def _wait_for_k3s_ready(
        conn: asyncssh.SSHClientConnection,
        timeout: int = 120
    ) -> Dict:
        """
        Wait for k3s to be ready

        Args:
            conn: SSH connection
            timeout: Timeout in seconds

        Returns:
            dict: Ready status
        """
        try:
            # Wait for k3s service to start
            wait_cmd = '''
            for i in {1..60}; do
                if sudo systemctl is-active --quiet k3s; then
                    echo "ready"
                    exit 0
                fi
                sleep 2
            done
            exit 1
            '''

            result = await conn.run(wait_cmd, timeout=timeout)

            if result.exit_status != 0:
                return {
                    'success': False,
                    'error': 'k3s service did not start within timeout'
                }

            # Wait for kubectl to work
            kubectl_wait = '''
            for i in {1..30}; do
                if sudo k3s kubectl get nodes > /dev/null 2>&1; then
                    exit 0
                fi
                sleep 2
            done
            exit 1
            '''

            kubectl_result = await conn.run(kubectl_wait, timeout=60)

            if kubectl_result.exit_status != 0:
                return {
                    'success': False,
                    'error': 'k3s API server did not become ready'
                }

            return {
                'success': True,
                'message': 'k3s is ready'
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Ready check failed: {str(e)}'
            }

    @staticmethod
    async def _get_kubeconfig(
        conn: asyncssh.SSHClientConnection,
        server_host: str
    ) -> Dict:
        """
        Retrieve kubeconfig from remote server

        Args:
            conn: SSH connection
            server_host: Server hostname/IP for API server URL

        Returns:
            dict: Kubeconfig content
        """
        try:
            # Get kubeconfig from server
            result = await conn.run('sudo cat /etc/rancher/k3s/k3s.yaml')

            if result.exit_status != 0:
                return {
                    'success': False,
                    'error': 'Failed to retrieve kubeconfig'
                }

            kubeconfig = result.stdout

            # Replace 127.0.0.1 with actual server host
            kubeconfig = kubeconfig.replace(
                'server: https://127.0.0.1:6443',
                f'server: https://{server_host}:6443'
            )

            return {
                'success': True,
                'kubeconfig': kubeconfig
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to get kubeconfig: {str(e)}'
            }

    @staticmethod
    async def _get_k3s_token(conn: asyncssh.SSHClientConnection) -> Dict:
        """
        Get k3s node token for joining workers

        Args:
            conn: SSH connection

        Returns:
            dict: Token content
        """
        try:
            result = await conn.run('sudo cat /var/lib/rancher/k3s/server/node-token')

            if result.exit_status == 0:
                return {
                    'success': True,
                    'token': result.stdout.strip()
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to retrieve k3s token'
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'token': None
            }

    @staticmethod
    async def uninstall_k3s(
        ssh_host: str,
        ssh_port: int,
        ssh_username: str,
        ssh_private_key: str,
        ssh_password: Optional[str] = None
    ) -> Dict:
        """
        Uninstall k3s from remote server

        Args:
            ssh_host: SSH hostname
            ssh_port: SSH port
            ssh_username: SSH username
            ssh_private_key: SSH private key
            ssh_password: Optional password

        Returns:
            dict: Uninstall result
        """
        try:
            # Connect
            conn_result = await K3sDeploymentService._connect_ssh(
                ssh_host, ssh_port, ssh_username, ssh_private_key, ssh_password
            )

            if not conn_result['success']:
                return conn_result

            conn = conn_result['connection']

            # Run uninstall script
            uid_result = await conn.run('id -u')
            sudo = '' if uid_result.stdout.strip() == '0' else 'sudo '

            result = await conn.run(f'{sudo}/usr/local/bin/k3s-uninstall.sh')
            await conn.close()

            if result.exit_status == 0:
                return {
                    'success': True,
                    'message': 'k3s uninstalled successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f'Uninstall failed: {result.stderr}'
                }

        except Exception as e:
            return {
                'success': False,
                'error': f'Uninstall error: {str(e)}'
            }
