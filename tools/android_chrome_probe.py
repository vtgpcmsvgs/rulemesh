"""通过已授权 ADB 读取 Chrome 的实际首页和搜索，禁用测试缓存并在 finally 恢复。"""
import sys,json,struct,os,base64,time,hashlib
class UsbAdbError(RuntimeError): pass
class LocalStream:
 def __init__(self,a,address):
  import socket,subprocess
  self.a=a;self.buf=bytearray();self.socket=None;self.port=None
  completed=subprocess.run([a.path,'-d','forward','tcp:0',address],capture_output=True,timeout=10)
  port=completed.stdout.strip()
  if completed.returncode or not port.isdigit():raise RuntimeError('Chrome ADB forwarding failed')
  self.port=int(port)
  try:
   self.socket=socket.create_connection(('127.0.0.1',self.port),timeout=10)
  except Exception:
   self.close();raise
 def send(self,data):self.socket.sendall(data)
 def read(self,n):
  while len(self.buf)<n:
   data=self.socket.recv(min(65536,n-len(self.buf)))
   if not data:raise RuntimeError('Chrome socket closed')
   self.buf.extend(data)
  data=bytes(self.buf[:n]);del self.buf[:n];return data
 def headers(self):
  data=bytearray()
  while not data.endswith(b'\r\n\r\n'):
   if len(data)>65536:raise RuntimeError('Chrome header limit exceeded')
   data.extend(self.read(1))
  return bytes(data)
 def close(self):
  import subprocess
  if self.socket:self.socket.close();self.socket=None
  if self.port:
   done=subprocess.run([self.a.path,'-d','forward','--remove','tcp:'+str(self.port)],capture_output=True,timeout=10)
   self.port=None
   if done.returncode:raise RuntimeError('Chrome forwarding cleanup failed')
class Stream:
 def __new__(cls,a,address):
  if not hasattr(a,'send'):return LocalStream(a,address)
  return super().__new__(cls)
 def __init__(self,a,address):
  self.a=a;self.buf=bytearray();a.local+=1;self.local=a.local;self.remote=None
  a.send(b'OPEN',self.local,0,address.encode()+b'\0')
  while True:
   cmd,x,y,data=a.receive()
   if y!=self.local and cmd==b'CLSE':continue
   assert y==self.local
   if cmd==b'CLSE':a.send(b'CLSE',self.local,x);raise UsbAdbError('Service unavailable')
   if cmd==b'OKAY':self.remote=x;break
 def accept(self):
  cmd,x,y,data=self.a.receive()
  if y!=self.local and cmd==b'CLSE':return cmd
  assert y==self.local
  if cmd==b'CLSE':raise UsbAdbError('Stream closed')
  if cmd==b'WRTE':self.buf.extend(data);self.a.send(b'OKAY',self.local,self.remote)
  return cmd
 def send(self,data):
  for offset in range(0,len(data),self.a.maximum):
   self.a.send(b'WRTE',self.local,self.remote,data[offset:offset+self.a.maximum])
   while self.accept()!=b'OKAY':pass
 def read(self,n):
  while len(self.buf)<n:self.accept()
  data=bytes(self.buf[:n]);del self.buf[:n];return data
 def headers(self):
  while b'\r\n\r\n' not in self.buf:self.accept()
  idx=self.buf.index(b'\r\n\r\n')+4;return self.read(idx)
 def close(self):
  self.a.send(b'CLSE',self.local,self.remote)
  while True:
   cmd,x,y,data=self.a.receive()
   if cmd==b'CLSE' and y==self.local:break
   if cmd==b'WRTE':self.a.send(b'OKAY',self.local,self.remote)
def tabs(a):
 s=Stream(a,'localabstract:chrome_devtools_remote');s.send(b'GET /json/list HTTP/1.1\r\nHost: localhost\r\n\r\n');h=s.headers()
 import re
 m=re.search(rb'(?i)Content-Length:\s*(\d+)',h);assert m,h.splitlines()[0]
 result=json.loads(s.read(int(m[1])));s.close();return result

def wait_tabs(a,seconds=10):
 deadline=time.monotonic()+seconds
 while True:
  try:return tabs(a)
  except UsbAdbError:
   if time.monotonic()>=deadline:raise
   time.sleep(.5)
class CDP:
 def __init__(self,a,target):
  self.s=Stream(a,'localabstract:chrome_devtools_remote');self.seq=0;self.events=[]
  key=base64.b64encode(os.urandom(16)).decode()
  self.s.send(('GET /devtools/page/'+target+' HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: '+key+'\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
  h=self.s.headers();assert b'101' in h.splitlines()[0]
 def send(self,obj):
  data=json.dumps(obj).encode();n=len(data);mask=os.urandom(4)
  h=bytes([0x81,0x80+n]) if n<126 else bytes([0x81,0x80+126])+struct.pack('!H',n)
  self.s.send(h+mask+bytes(v^mask[i%4] for i,v in enumerate(data)))
 def recv(self):
  h=self.s.read(2);n=h[1]&127
  if n==126:n=struct.unpack('!H',self.s.read(2))[0]
  if n==127:n=struct.unpack('!Q',self.s.read(8))[0]
  data=self.s.read(n)
  assert h[0]&15==1,'Non text frame'
  return json.loads(data)
 def call(self,method,params=None):
  self.seq+=1;self.send({'id':self.seq,'method':method,'params':params or {}})
  while True:
   data=self.recv()
   if data.get('id')==self.seq:
    assert 'error' not in data,'CDP command rejected'
    return data.get('result',{})
   self.events.append(data)
   if len(self.events)>5000:raise RuntimeError("Chrome event limit exceeded")
 def close(self):self.s.close()

def audit_page(page, documents, path):
 return (page.get('host') in {'google.com','www.google.com'} and page.get('path')==path
         and page.get('ready')=='complete' and page.get('search') is True and page.get('error') is False
         and any(d.get('host') in {'google.com','www.google.com'} and d.get('path')==path
                 and d.get('status')==200 and d.get('https') and d.get('tls') and not d.get('cached') for d in documents))

def probe(a):
 from urllib.parse import urlsplit
 a.shell('monkey -p com.android.chrome -c android.intent.category.LAUNCHER 1')
 time.sleep(1)
 if not any('mCurrentFocus=' in line and 'com.android.chrome/' in line for line in a.shell('dumpsys window').splitlines()):
  raise RuntimeError('Chrome foreground required')
 targets=wait_tabs(a)
 pages=[t for t in targets if t.get('type')=='page']
 if len(pages)!=1:raise RuntimeError('Unique Chrome page required')
 c=CDP(a,pages[0]['id']);rows=[]
 try:
  c.call('Network.enable');c.call('Page.enable');c.call('Page.bringToFront')
  c.call('Network.setCacheDisabled',{'cacheDisabled':True})
  for path in ('/','/search'):
   c.events=[]
   nav=c.call('Page.navigate',{'url':'https://www.google.com'+path+('?q=rulemesh+acceptance' if path=='/search' else '')})
   deadline=time.monotonic()+22;passed=False;documents=[];page={}
   while time.monotonic()<deadline:
    time.sleep(1)
    raw=c.call('Runtime.evaluate',{'expression':'JSON.stringify({host:location.hostname,path:location.pathname,ready:document.readyState,search:!!document.querySelector("textarea[name=q],input[name=q]"),error:!!document.querySelector("#main-frame-error")})','returnByValue':True})
    page=json.loads(raw['result']['value']);documents=[]
    for event in c.events:
     params=event.get('params',{})
     if event.get('method')=='Network.responseReceived' and params.get('type')=='Document':
      r=params['response'];u=urlsplit(r['url'])
      documents.append({'host':u.hostname,'path':u.path,'status':r['status'],'https':u.scheme=='https',
                        'tls':bool(r.get('securityDetails',{}).get('issuer')),'cached':r.get('fromDiskCache',False) or r.get('fromServiceWorker',False)})
    passed=audit_page(page,documents,path) and not nav.get('errorText')
    if passed:break
   rows.append({'path':path,'passed':bool(passed),'google_com':page.get('host') in {'google.com','www.google.com'},
                'path_matched':page.get('path')==path,'search_input':page.get('search') is True,
                'trusted_uncached_https_200':any(d['https'] and d['tls'] and d['status']==200 and not d['cached'] for d in documents)})
 finally:
  try:c.call('Network.setCacheDisabled',{'cacheDisabled':False})
  finally:c.close()
 return {'passed':len(rows)==2 and all(r['passed'] for r in rows),'pages':rows,'cache_restored':True}
