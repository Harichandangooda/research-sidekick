"""Write markers, recreate StatefulSet Pods, verify both markers, then clean up."""
import json
import subprocess
import sys
import uuid

namespace = sys.argv[1] if len(sys.argv) > 1 else 'research-sidekick'


def kubectl(*args):
    return subprocess.check_output(['kubectl', '-n', namespace, *args], text=True)


def backend_python(code):
    # Argument lists preserve Python/SQL quoting across Windows and Linux.
    return kubectl('exec', 'deployment/backend', '--', 'python', '-c', code)


marker = uuid.uuid4().hex
collection = 'persistence_' + marker
email = marker + '@persistence.invalid'
print('Creating isolated MySQL and Chroma markers')
backend_python(f'''
from backend.storage import session_store
from backend.storage.rag_store import get_client
session_store.create_user({email!r}, "persistence-test")
get_client().create_collection({collection!r}).add(
    ids=["marker"], documents=[{marker!r}], embeddings=[[1.0, 0.0]])
''')
before = json.loads(kubectl('get', 'pvc', '-o', 'json'))
uids = {obj['metadata']['name']: obj['metadata']['uid'] for obj in before['items']}
print(kubectl('delete', 'pod', 'mysql-0', 'chromadb-0'))
for name in ('mysql-0', 'chromadb-0'):
    print(kubectl('wait', '--for=condition=Ready', 'pod/' + name, '--timeout=300s'))
print(kubectl('rollout', 'status', 'deployment/backend', '--timeout=300s'))
backend_python(f'''
import time
from backend.storage import session_store
from backend.storage.rag_store import get_client
for attempt in range(60):
    try:
        assert session_store.get_user_with_password({email!r})
        result = get_client().get_collection({collection!r}).get(ids=["marker"])
        assert result["documents"] == [{marker!r}]
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(2)
with session_store.get_connection() as conn:
    conn.execute("DELETE FROM users WHERE email = ?", ({email!r},))
get_client().delete_collection({collection!r})
print("MySQL row and Chroma document survived Pod recreation")
''')
after = json.loads(kubectl('get', 'pvc', '-o', 'json'))
assert uids == {obj['metadata']['name']: obj['metadata']['uid'] for obj in after['items']}
print('PASS: original PVCs retained; persistence markers verified and removed')
