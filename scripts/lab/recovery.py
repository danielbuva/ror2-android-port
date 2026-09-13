from common import *
import re,time,urllib.request,urllib.parse,shutil

def decompile(assembly=None,force=False):
 version=run([ROOT/'scripts/ilspycmd','--version']).stdout.decode()
 if '11.0.0.9375' not in version:raise RuntimeError('ilspycmd pin changed; review cache/tool compatibility')
 base=game()/'Risk of Rain 2_Data/Managed'; results=[]
 paths=[base/assembly] if assembly else sorted(base.glob('*.dll'))
 for p in paths:
  if p.parent!=base or not p.is_file():raise RuntimeError('Assembly must be a filename in Managed')
  key=digest({'input':sha(p),'ilspy':'11.0.0.9375','args':'project-referencepath-csharp9-v2'})
  dest=WORK/'decompiled'/p.stem/key[:16]; status=dest/'result.json'
  if status.exists() and read(status).get('success') and not force:results.append(read(status));continue
  if dest.exists() and force: dest=dest.parent/(key[:16]+'-'+now())
  dest.mkdir(parents=True,exist_ok=True);started=time.monotonic()
  try:
   proc=run([ROOT/'scripts/ilspycmd','--disable-updatecheck','-lv','CSharp9_0','-p','-r',base,'-o',dest,p],timeout=300,check=False)
   (dest/'decompile.log').write_bytes(proc.stdout+proc.stderr)
   sources=list(dest.rglob('*.cs'));diagnostics=[];counts={k:0 for k in ['unsafe','platform_conditionals','reflection_emit','decompiler_failure','invalid_il']}
   for f in sources:
    t=f.read_text(errors='replace')
    for k,pattern in {'unsafe':r'\bunsafe\b','platform_conditionals':r'#if.*(?:UNITY_|WIN|ANDROID)','reflection_emit':r'Reflection.Emit|DynamicMethod|AssemblyBuilder','decompiler_failure':r'Could not decompile|DecompilerException','invalid_il':r'Invalid IL|Unknown result type|Expected [IO], but got'}.items():
     n=len(re.findall(pattern,t));counts[k]+=n
     if n and k in ['decompiler_failure','invalid_il']:diagnostics.append({'file':str(f.relative_to(dest)),'category':k,'count':n})
   result={'assembly':p.name,'input_sha256':sha(p),'cache_key':key,'output':str(dest.relative_to(ROOT)),'success':proc.returncode==0,'exit_code':proc.returncode,'source_files':len(sources),'seconds':time.monotonic()-started,'counts':counts,'diagnostics':diagnostics}
  except Exception as e:result={'assembly':p.name,'success':False,'error':str(e),'output':str(dest.relative_to(ROOT))}
  write(status,result);results.append(result);write(WORK/'inventory/decompilation.json',results)
  print(p.name,result.get('source_files'),result['success'],flush=True)
 write(WORK/'inventory/decompilation.json',results)

def post(endpoint,data,timeout=1800):
 req=urllib.request.Request('http://127.0.0.1:8081'+endpoint,data=urllib.parse.urlencode(data).encode())
 return urllib.request.urlopen(req,timeout=timeout).read()

def export_project(force=False):
 inv=read(WORK/'inventory/files.json');key=digest({'input':inv['input_id'],'assetripper':'2.0.0+1ac666f','settings':read(ROOT/'tools/assetripper-settings.json')})
 dest=WORK/'assetripper'/key[:16];status=dest/'result.json'
 if status.exists() and read(status).get('success') and not force:
  cached=read(status)
  if not all((ROOT/p/'ProjectSettings/ProjectVersion.txt').exists() for p in cached.get('projects',[])):raise RuntimeError('Cached export missing project; use --force for a new export')
  write(WORK/'config/reconstruction.json',cached);print(json.dumps(cached,indent=2));return
 if dest.exists():dest=dest.parent/(key[:16]+'-'+now())
 dest.mkdir(parents=True);start=time.monotonic();result={'key':key,'input_id':inv['input_id'],'output':str(dest.relative_to(ROOT)),'success':False}
 try:
  # Dedicated loopback server, never sends input paths or contents to a remote service.
  try:urllib.request.urlopen('http://127.0.0.1:8081/',timeout=2).close()
  except OSError:
   service=WORK/'assetripper-service';service.mkdir(exist_ok=True)
   logfile=service/'service.log'
   with logfile.open('ab') as log:
    proc=subprocess.Popen([str(ROOT/'scripts/assetripper'),'--headless','--port','8081','--log-path',str(service/'export.log')],cwd=service,stdout=log,stderr=log,start_new_session=True)
   write(service/'process.json',{'pid':proc.pid})
   for _ in range(30):
    try:urllib.request.urlopen('http://127.0.0.1:8081/',timeout=2).close();break
    except OSError:time.sleep(1)
   else:raise RuntimeError('AssetRipper service startup failed: '+str(logfile))
  post('/Reset',{})
  post('/Settings/Update',{k:v for k,v in read(ROOT/'tools/assetripper-settings.json').items() if v!='false'})
  (dest/'settings.html').write_bytes(urllib.request.urlopen('http://127.0.0.1:8081/Settings/Edit').read())
  (dest/'load-response.html').write_bytes(post('/LoadFolder',{'Path':str(game())}))
  (dest/'export-response.html').write_bytes(post('/Export/UnityProject',{'Path':str(dest/'export'),'CreateSubfolder':'false'}))
  projects=list((dest/'export').rglob('ProjectVersion.txt'))
  result['projects']=[str(p.parent.parent.relative_to(ROOT)) for p in projects];result['success']=bool(projects)
  if result['success']:write(WORK/'config/reconstruction.json',result)
 except Exception as e:result['error']=str(e)
 result['seconds']=time.monotonic()-start;write(status,result);print(json.dumps(result,indent=2))
 if not result['success']:raise RuntimeError('AssetRipper export failed; see '+str(status))
