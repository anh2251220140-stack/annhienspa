"""Report secret presence only; never print values or matching lines."""
import json,os,subprocess
from pathlib import Path
from dotenv import load_dotenv
root=Path(__file__).resolve().parents[1]
load_dotenv(root/'.env')
def git(*args):
    return subprocess.check_output(['git',*args],cwd=root)
names=('PAYOS_CLIENT_ID','PAYOS_API_KEY','PAYOS_CHECKSUM_KEY','DJANGO_SECRET_KEY','MYSQL_PASSWORD','EMAIL_HOST_PASSWORD')
secrets={name:os.getenv(name,'').encode() for name in names if len(os.getenv(name,''))>=8}
paths=git('ls-files','--cached','--others','--exclude-standard','-z').decode().split('\0')
matches=[]
for name in filter(None,paths):
    path=root/name
    if not path.is_file():continue
    data=path.read_bytes()
    found=[key for key,value in secrets.items() if value in data]
    if found:matches.append({'path':name,'variables':found})
index_matches=[]
for name in filter(None,git('ls-files','-z').decode().split('\0')):
    data=git('show',':'+name)
    found=[key for key,value in secrets.items() if value in data]
    if found:index_matches.append({'path':name,'variables':found})
history_matches=[]
for line in git('rev-list','--objects','--all').decode().splitlines():
    oid=line.split(' ',1)[0]
    if git('cat-file','-t',oid).strip()!=b'blob':continue
    data=git('cat-file','blob',oid)
    found=[key for key,value in secrets.items() if value in data]
    if found:history_matches.append({'object':oid,'variables':found})
tracked_env=[p for p in paths if p and Path(p).name.startswith('.env') and Path(p).name!='.env.example']
history_env=[p for p in git('log','--all','--format=','--name-only','--','.env','**/.env').decode().splitlines() if p]
print(json.dumps(dict(envIgnored=subprocess.run(['git','check-ignore','-q','.env'],cwd=root).returncode==0,
    trackedOrUnignoredEnv=tracked_env,envHistoryPaths=sorted(set(history_env)),
    checkedVariableNames=list(secrets),workingTreeMatches=matches,indexMatches=index_matches,historyMatches=history_matches),indent=2))
