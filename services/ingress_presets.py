"""
Ingress template presets for common deployment patterns
"""

PRESETS = {
    'external-proxy': {
        'name': 'External Service Proxy',
        'description': 'Proxy to a service running outside Kubernetes (like Hostinger, external VPS, etc)',
        'icon': 'fa-server',
        'spec': {
            'enabled': True,
            'tls': {
                'enabled': True,
                'useWildcard': True,
                'wildcardSecretName': 'wildcard-comunatec-org-tls'
            },
            'backend': {
                'type': 'external',
                'externalPort': 80,
                'externalHttpsPort': 443
            },
            'annotations': {
                'traefik.ingress.kubernetes.io/router.entrypoints': 'web,websecure'
            },
            'ingressClassName': 'traefik'
        },
        'required_fields': ['host', 'backend.externalIP'],
        'example': {
            'host': 'loja.comunatec.org',
            'backend.externalIP': '76.13.89.244'
        }
    },

    'standard-app': {
        'name': 'Standard Application',
        'description': 'Internal K8s service with automatic TLS certificate and HTTP to HTTPS redirect',
        'icon': 'fa-cube',
        'spec': {
            'enabled': True,
            'tls': {
                'enabled': True,
                'clusterIssuer': 'letsencrypt-prod',
                'useWildcard': False
            },
            'backend': {
                'type': 'service'
            },
            'annotations': {
                'traefik.ingress.kubernetes.io/router.entrypoints': 'web,websecure'
            },
            'ingressClassName': 'traefik'
        },
        'required_fields': ['host', 'backend.serviceName', 'backend.servicePort'],
        'example': {
            'host': 'app.comunatec.org',
            'backend.serviceName': 'my-app',
            'backend.servicePort': 8080
        }
    },

    'standard-app-wildcard': {
        'name': 'Standard App (Wildcard TLS)',
        'description': 'Internal K8s service using existing wildcard certificate (faster, no cert-manager delay)',
        'icon': 'fa-certificate',
        'spec': {
            'enabled': True,
            'tls': {
                'enabled': True,
                'useWildcard': True,
                'wildcardSecretName': 'wildcard-comunatec-org-tls'
            },
            'backend': {
                'type': 'service'
            },
            'annotations': {
                'traefik.ingress.kubernetes.io/router.entrypoints': 'web,websecure'
            },
            'ingressClassName': 'traefik'
        },
        'required_fields': ['host', 'backend.serviceName', 'backend.servicePort'],
        'example': {
            'host': 'app.comunatec.org',
            'backend.serviceName': 'my-app',
            'backend.servicePort': 8080
        }
    },

    'multi-path': {
        'name': 'Multi-Path Routing',
        'description': 'Route different URL paths to different services (e.g., /api → api-service, / → frontend-service)',
        'icon': 'fa-code-branch',
        'spec': {
            'enabled': True,
            'tls': {
                'enabled': True,
                'clusterIssuer': 'letsencrypt-prod'
            },
            'backend': {
                'type': 'service',
                'serviceName': 'default-backend',
                'servicePort': 80
            },
            'paths': [
                {
                    'path': '/api',
                    'pathType': 'Prefix',
                    'serviceName': 'api-service',
                    'servicePort': 8080,
                    'priority': 10
                },
                {
                    'path': '/',
                    'pathType': 'Prefix',
                    'serviceName': 'frontend-service',
                    'servicePort': 80,
                    'priority': 1
                }
            ],
            'annotations': {
                'traefik.ingress.kubernetes.io/router.entrypoints': 'web,websecure'
            },
            'ingressClassName': 'traefik'
        },
        'required_fields': ['host'],
        'example': {
            'host': 'app.comunatec.org',
            'paths[0].serviceName': 'api-backend',
            'paths[0].servicePort': 8080,
            'paths[1].serviceName': 'web-frontend',
            'paths[1].servicePort': 3000
        }
    },

    'http-only': {
        'name': 'HTTP Only (No TLS)',
        'description': 'Simple HTTP ingress without encryption (not recommended for production)',
        'icon': 'fa-unlock',
        'spec': {
            'enabled': True,
            'tls': {
                'enabled': False
            },
            'backend': {
                'type': 'service'
            },
            'annotations': {
                'traefik.ingress.kubernetes.io/router.entrypoints': 'web'
            },
            'ingressClassName': 'traefik'
        },
        'required_fields': ['host', 'backend.serviceName', 'backend.servicePort'],
        'example': {
            'host': 'internal-app.local',
            'backend.serviceName': 'internal-service',
            'backend.servicePort': 8080
        }
    },

    'custom': {
        'name': 'Custom Configuration',
        'description': 'Start with empty template and configure all options manually',
        'icon': 'fa-cog',
        'spec': {
            'enabled': True,
            'tls': {
                'enabled': False
            },
            'backend': {
                'type': 'service'
            },
            'ingressClassName': 'traefik'
        },
        'required_fields': ['host', 'backend'],
        'example': {}
    }
}


def get_preset(preset_id: str) -> dict:
    """Get a preset by ID"""
    return PRESETS.get(preset_id)


def list_presets() -> dict:
    """List all available presets"""
    return PRESETS


def get_preset_names() -> list:
    """Get list of preset IDs and names"""
    return [
        {
            'id': key,
            'name': preset['name'],
            'description': preset['description'],
            'icon': preset.get('icon', 'fa-file')
        }
        for key, preset in PRESETS.items()
    ]


def merge_preset_with_values(preset_id: str, values: dict) -> dict:
    """
    Merge a preset spec with user-provided values
    Returns complete spec ready for IngressTemplate creation
    """
    preset = get_preset(preset_id)
    if not preset:
        raise ValueError(f"Unknown preset: {preset_id}")

    # Start with preset spec
    spec = preset['spec'].copy()

    # Deep merge values
    def deep_merge(base, updates):
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                deep_merge(base[key], value)
            else:
                base[key] = value

    deep_merge(spec, values)

    return spec
