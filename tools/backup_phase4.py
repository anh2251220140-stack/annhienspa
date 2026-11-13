"""Local backup; excludes secrets and verifies archive/dump. Never prints credentials."""
import os,sys,zipfile,hashlib,json,subprocess,tempfile
from pathlib import Path
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
import django;django.setup()
from django.conf import settings
root=settings.BASE_DIR;db=settings.DATABASES["default"]
assert db["NAME"]=="annhien_spa"
out=root/"backups"/("phase4-"+datetime.now().strftime("%Y%m%d-%H%M%S"));out.mkdir(parents=True)
exclude={".git",".venv","backups","__pycache__",".codex",".agents",".figma","node_modules","staticfiles"}
with zipfile.ZipFile(out/"source.zip","w",zipfile.ZIP_DEFLATED) as z:
 for p in root.rglob("*"):
  rel=p.relative_to(root)
  if p.is_file() and not any(x in exclude for x in rel.parts) and not p.name.startswith(".env") and p.suffix not in {".sql",".cnf",".log",".pyc",".key",".pem"}:z.write(p,rel)
with zipfile.ZipFile(out/"source.zip") as z:assert z.testzip() is None
fd,name=tempfile.mkstemp(suffix=".cnf")
def quote(value):return '"'+str(value).replace('\\','\\\\').replace('"','\\"')+'"'
try:
 with os.fdopen(fd,"w",encoding="utf-8") as f:
  f.write("[client]\n"+"\n".join(k+"="+quote(v) for k,v in {"user":db["USER"],"password":db["PASSWORD"],"host":db["HOST"],"port":db["PORT"]}.items()))
 with (out/"database.sql").open("wb") as f:
  r=subprocess.run([r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe","--defaults-extra-file="+name,"--single-transaction","--no-tablespaces","--set-gtid-purged=OFF","--skip-add-drop-table",db["NAME"]],stdout=f,stderr=subprocess.PIPE)
 if r.returncode:raise RuntimeError("mysqldump failed; credentials were not logged")
finally:os.unlink(name)
assert b"Dump completed" in (out/"database.sql").read_bytes()[-2048:]
(out/"verification.json").write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()},indent=2))
print("Verified backup:",out.name)
