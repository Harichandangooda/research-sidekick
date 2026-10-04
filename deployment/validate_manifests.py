"""Check raw and Helm-rendered wiring without needing a running cluster."""
from pathlib import Path
import re
import sys

import yaml


def validate(directory):
    resources = {}
    for path in Path(directory).rglob('*.yaml'):
        if path.name.endswith('.example.yaml'):
            continue
        for obj in yaml.safe_load_all(path.read_text(encoding='utf-8-sig')):
            if obj:
                resources[obj['kind'], obj['metadata']['name']] = obj
    workloads = [obj for (kind, _), obj in resources.items()
                 if kind in ('Deployment', 'StatefulSet')]
    assert len(workloads) == 4, 'Expected four application workloads'
    for obj in workloads:
        spec = obj['spec']
        labels = spec['template']['metadata']['labels']
        assert all(labels.get(k) == v for k, v in spec['selector']['matchLabels'].items())
        container = spec['template']['spec']['containers'][0]
        image = container['image']
        assert ':' in image and not image.endswith(':latest'), image
        if obj['kind'] == 'StatefulSet':
            assert spec['replicas'] == 1
            claims = {claim['metadata']['name'] for claim in spec['volumeClaimTemplates']}
            assert container['volumeMounts'][0]['name'] in claims
            expected = '/var/lib/mysql' if obj['metadata']['name'] == 'mysql' else '/data'
            assert container['volumeMounts'][0]['mountPath'] == expected
            assert ('Service', spec['serviceName']) in resources
    services = {name: obj for (kind, name), obj in resources.items() if kind == 'Service'}
    assert len(services) == 4
    for service in services.values():
        assert service['spec']['type'] == 'ClusterIP'
        matches = [obj for obj in workloads if all(
            obj['spec']['template']['metadata']['labels'].get(k) == v
            for k, v in service['spec']['selector'].items())]
        assert len(matches) == 1
        container = matches[0]['spec']['template']['spec']['containers'][0]
        assert service['spec']['ports'][0]['targetPort'] == container['ports'][0]['containerPort']
    config = resources['ConfigMap', 'backend-config']['data']
    for prefix in ('MYSQL', 'CHROMA'):
        service = services[config[f'{prefix}_HOST']]
        assert int(config[f'{prefix}_PORT']) == service['spec']['ports'][0]['port']
    backend = resources['Deployment', 'backend']['spec']['template']['spec']['containers'][0]
    assert backend['envFrom'] == [
        {'configMapRef': {'name': 'backend-config'}},
        {'secretRef': {'name': 'backend-secret'}}]
    assert {env['name'] for env in backend['env']} == {'MYSQL_USER', 'MYSQL_PASSWORD'}
    for env in backend['env']:
        assert env['valueFrom']['secretKeyRef'] == {'name': 'mysql-secret', 'key': env['name']}
    for probe, path in [('livenessProbe', '/health/live'), ('readinessProbe', '/health/ready')]:
        assert backend[probe]['httpGet'] == {'path': path, 'port': 8000}
    assert not any('PASSWORD' in key or 'SECRET' in key or 'API_KEY' in key for key in config)
    ingress = resources['Ingress', 'research-sidekick']
    assert ingress['metadata']['annotations']['nginx.ingress.kubernetes.io/rewrite-target'] == '/$2'
    paths = ingress['spec']['rules'][0]['http']['paths']
    for route in paths:
        target = route['backend']['service']
        assert target['port']['number'] == services[target['name']]['spec']['ports'][0]['port']
    for url, expected in [('/api/auth/login', ('backend-service', '/auth/login')),
                          ('/api/health/ready', ('backend-service', '/health/ready')),
                          ('/api', ('backend-service', '/')),
                          ('/', ('frontend-service', '/')),
                          ('/static/js/main.js', ('frontend-service', '/static/js/main.js'))]:
        for route in paths:
            match = re.match('^' + route['path'], url)
            if match:
                assert (route['backend']['service']['name'], '/' + match.group(2)) == expected
                break
        else:
            raise AssertionError(f'No route for {url}')
    print(f'{directory}: {len(resources)} resources; selectors, ports, DNS, secrets, PVCs, probes and routes pass')
    return resources


if __name__ == '__main__':
    raw = validate(sys.argv[1] if len(sys.argv) > 1 else 'k8s')
    if len(sys.argv) > 2:
        rendered = validate(sys.argv[2])
        raw.pop(('Namespace', 'research-sidekick'), None)
        assert raw == rendered, 'Default Helm output differs from raw manifests'
        print('Default Helm resources match raw manifests exactly')
