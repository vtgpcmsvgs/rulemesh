"""授权 USB ADB 的显式 Windows 后备传输；依赖外部同位数 AdbWinApi，不修改授权密钥。"""
import ctypes as C
from ctypes import wintypes as W
import pathlib,struct,time,base64,re
class UsbAdbError(RuntimeError):pass
class UsbAdb:
 def __init__(self, api_directory, key_directory=None):
  self.r=self.w=self.i=None;self._mutex=None
  self._mutex_api=C.WinDLL('kernel32',use_last_error=True)
  self._mutex_api.CreateMutexW.argtypes=[C.c_void_p,W.BOOL,W.LPCWSTR];self._mutex_api.CreateMutexW.restype=C.c_void_p
  self._mutex_api.WaitForSingleObject.argtypes=[C.c_void_p,W.DWORD];self._mutex_api.WaitForSingleObject.restype=W.DWORD
  self._mutex_api.ReleaseMutex.argtypes=[C.c_void_p];self._mutex_api.ReleaseMutex.restype=W.BOOL
  self._mutex_api.CloseHandle.argtypes=[C.c_void_p];self._mutex_api.CloseHandle.restype=W.BOOL
  mutex=self._mutex_api.CreateMutexW(None,False,'Local\\RuleMeshAuthorizedUsbAdb')
  if not mutex:raise UsbAdbError('USB serialization guard unavailable')
  if self._mutex_api.WaitForSingleObject(mutex,0) not in (0,128):
   self._mutex_api.CloseHandle(mutex);raise UsbAdbError('Another task USB session is active; wait for its completion')
  self._mutex=mutex
  root=pathlib.Path(api_directory).resolve()
  self.key_directory=pathlib.Path(key_directory).resolve() if key_directory else pathlib.Path.home()/'.android'
  if not all((root/name).is_file() for name in ('AdbWinApi.dll','AdbWinUsbApi.dll')):raise UsbAdbError('Explicit USB API directory is incomplete')
  class GUID(C.Structure):_fields_=[('a',W.DWORD),('b',W.WORD),('c',W.WORD),('d',C.c_ubyte*8)]
  guid=GUID(0xf72fe0d4,0xcbcb,0x407d,(C.c_ubyte*8)(0x88,0x14,0x9e,0xd6,0x73,0xd0,0xdd,0x6b))
  kernel=C.WinDLL('kernel32',use_last_error=True)
  kernel.SetDllDirectoryW.argtypes=[W.LPCWSTR]
  kernel.SetDllDirectoryW(str(root))
  self.dll=C.CDLL(str(root/'AdbWinApi.dll'),use_last_error=True)
  def api(name,args,ret):
   f=getattr(self.dll,name);f.argtypes=args;f.restype=ret;return f
  h=C.c_void_p
  self.close_handle=api('AdbCloseHandle',[h],C.c_bool)
  enum=api('AdbEnumInterfaces',[GUID,C.c_bool,C.c_bool,C.c_bool],h)
  nxt=api('AdbNextInterface',[h,h,C.POINTER(W.ULONG)],C.c_bool)
  create=api('AdbCreateInterfaceByName',[W.LPCWSTR],h)
  orp=api('AdbOpenDefaultBulkReadEndpoint',[h,C.c_int,C.c_int],h)
  owp=api('AdbOpenDefaultBulkWriteEndpoint',[h,C.c_int,C.c_int],h)
  self.read_api=api('AdbReadEndpointSync',[h,h,W.ULONG,C.POINTER(W.ULONG),W.ULONG],C.c_bool)
  self.write_api=api('AdbWriteEndpointSync',[h,h,W.ULONG,C.POINTER(W.ULONG),W.ULONG],C.c_bool)
  self.local=0;self.maximum=4096
  e=enum(guid,True,True,True)
  if not e:raise UsbAdbError('USB enumeration failed')
  names=[]
  try:
   while True:
    b=C.create_string_buffer(4096);size=W.ULONG(len(b))
    if not nxt(e,b,C.byref(size)):break
    names.append(C.wstring_at(C.addressof(b)+20))
  finally:self.close_handle(e)
  if len(names)!=1:raise UsbAdbError('Expected exactly one USB debugging interface')
  self.i=create(names[0])
  if not self.i:raise UsbAdbError('USB interface open failed (Win32 '+str(C.get_last_error())+')')
  self.r=orp(self.i,0,0);self.w=owp(self.i,0,0)
  if not self.r or not self.w:self.close();raise UsbAdbError('USB endpoint access denied')
  # Drain a previous incomplete handshake before starting a new authenticated session.
  for _ in range(10):
   b=C.create_string_buffer(65536);n=W.ULONG()
   if not self.read_api(self.r,b,len(b),C.byref(n),100) or not n.value:break
 def close(self):
  for name in ('r','w','i'):
   h=getattr(self,name,None)
   if h:self.close_handle(h);setattr(self,name,None)
  if getattr(self,'_mutex',None):
   self._mutex_api.ReleaseMutex(self._mutex);self._mutex_api.CloseHandle(self._mutex);self._mutex=None
 def __del__(self):self.close()
 def __enter__(self):return self
 def __exit__(self,*args):self.close()
 def _write(self,block):
  b=C.create_string_buffer(block);n=W.ULONG()
  if not self.write_api(self.w,b,len(block),C.byref(n),5000) or n.value!=len(block):raise UsbAdbError('USB write failed')
  if block and len(block)%512==0:
   empty=C.create_string_buffer(1);n=W.ULONG()
   if not self.write_api(self.w,empty,0,C.byref(n),5000):raise UsbAdbError('USB zero length write failed')
 def send(self,command,a0=0,a1=0,payload=b''):
  cmd=int.from_bytes(command,'little');header=struct.pack('<6I',cmd,a0,a1,len(payload),sum(payload)&0xffffffff,cmd^0xffffffff)
  self._write(header)
  if payload:self._write(payload)
 def _read_exact(self,size,timeout=8000):
  result=bytearray()
  while len(result)<size:
   b=C.create_string_buffer(size-len(result));n=W.ULONG()
   if not self.read_api(self.r,b,len(b),C.byref(n),timeout):raise UsbAdbError('USB read failed or authorization pending')
   if not n.value:raise UsbAdbError('USB stream closed')
   result.extend(b.raw[:n.value])
  return bytes(result)
 def receive(self,timeout=8000):
  h=struct.unpack('<6I',self._read_exact(24,timeout));cmd,a0,a1,size,checksum,magic=h
  if magic!=(cmd^0xffffffff) or size>1024*1024:raise UsbAdbError('Invalid USB ADB frame')
  payload=self._read_exact(size,timeout) if size else b''
  if sum(payload)&0xffffffff!=checksum:raise UsbAdbError('USB ADB checksum mismatch')
  return cmd.to_bytes(4,'little'),a0,a1,payload
 def _rsa_private(self):
  raw=(self.key_directory/'adbkey').read_bytes()
  der=base64.b64decode(b''.join(line for line in raw.splitlines() if not line.startswith(b'-')))
  def item(data,index=0):
   tag=data[index];length=data[index+1];offset=index+2
   if length&128:
    k=length&127;length=int.from_bytes(data[offset:offset+k],'big');offset+=k
   return tag,data[offset:offset+length],offset+length
  _,body,_=item(der);tag,version,offset=item(body)
  tag,first,next_offset=item(body,offset)
  if tag==0x30:
   tag,octets,_=item(body,next_offset)
   if tag!=4:raise UsbAdbError('Unsupported ADB key format')
   _,body,_=item(octets);_,_,offset=item(body)
  values=[]
  while offset<len(body):
   tag,value,offset=item(body,offset)
   if tag!=2:raise UsbAdbError('Unsupported ADB RSA format')
   values.append(int.from_bytes(value,'big'))
  if len(values)<3:raise UsbAdbError('Incomplete ADB RSA key')
  return values[0],values[2]
 def connect(self):
  self.send(b'CNXN',0x01000000,4096,b'host::\0');signed=False;public=False
  deadline=time.monotonic()+35
  while time.monotonic()<deadline:
   command,a0,a1,data=self.receive(10000)
   if command==b'CNXN':self.maximum=min(a1,4096);return
   if command==b'CLSE':continue
   if command in (b'WRTE',b'OKAY'):
    self.send(b'CLSE',a1,a0);continue
   if command!=b'AUTH' or a0!=1:raise UsbAdbError('Unexpected USB authentication reply')
   if not signed:
    n,d=self._rsa_private();size=(n.bit_length()+7)//8;digest=bytes.fromhex('3021300906052b0e03021a05000414')+data
    block=b'\0\1'+b'\xff'*(size-len(digest)-3)+b'\0'+digest;signature=pow(int.from_bytes(block,'big'),d,n).to_bytes(size,'big')
    self.send(b'AUTH',2,0,signature);signed=True
   elif not public:
    key=(self.key_directory/'adbkey.pub').read_bytes().rstrip(b'\0\r\n')+b'\0';self.send(b'AUTH',3,0,key);public=True
   else:raise UsbAdbError('USB debugging authorization required')
  raise UsbAdbError('USB debugging authorization timed out')
 def service(self,address,deadline_seconds=25):
  self.local+=1;local=self.local;remote=0;output=bytearray();self.send(b'OPEN',local,0,address.encode()+b'\0');deadline=time.monotonic()+deadline_seconds
  while time.monotonic()<deadline:
   cmd,a0,a1,data=self.receive(max(1,int((deadline-time.monotonic())*1000)))
   if a1!=local:
    if cmd==b'CLSE' and a1<local:continue
    raise UsbAdbError('Unexpected USB stream '+cmd.decode('ascii','replace')+' '+str(a0)+'/'+str(a1)+' expected '+str(local))
   remote=a0
   if cmd==b'OKAY':continue
   if cmd==b'WRTE':
    output.extend(data)
    if len(output)>16*1024*1024:raise UsbAdbError('USB shell output limit exceeded')
    self.send(b'OKAY',local,remote)
   elif cmd==b'CLSE':self.send(b'CLSE',local,remote);return bytes(output)
   else:raise UsbAdbError('Unexpected USB shell reply')
  raise UsbAdbError('USB shell deadline exceeded')
 def shell(self,command,deadline_seconds=25):return self.service('shell:'+command,deadline_seconds).decode('utf-8','replace')
 def exchange(self,address,request,deadline_seconds=30,max_bytes=16*1024*1024):
  self.local+=1;local=self.local;remote=0;output=bytearray();offset=0;self.send(b'OPEN',local,0,address.encode()+b'\0');deadline=time.monotonic()+deadline_seconds
  while time.monotonic()<deadline:
   cmd,a0,a1,data=self.receive(max(1,int((deadline-time.monotonic())*1000)))
   if a1!=local:
    if cmd==b'CLSE' and a1<local:continue
    raise UsbAdbError('Unexpected stream in USB exchange')
   remote=a0
   if cmd==b'OKAY':
    if offset<len(request):
     chunk=request[offset:offset+self.maximum];offset+=len(chunk);self.send(b'WRTE',local,remote,chunk)
   elif cmd==b'WRTE':
    output.extend(data);self.send(b'OKAY',local,remote)
    if len(output)>max_bytes:raise UsbAdbError('USB exchange output limit exceeded')
   elif cmd==b'CLSE':
    self.send(b'CLSE',local,remote)
    if offset!=len(request):raise UsbAdbError('USB exchange input was truncated')
    return bytes(output)
   else:raise UsbAdbError('Unexpected USB exchange reply')
  raise UsbAdbError('USB exchange deadline exceeded')
 def http(self,port,path,secret=''):
  import json
  if not isinstance(port,int) or not 1024<=port<=65535 or not path.startswith('/'):raise UsbAdbError('Invalid explicit controller request')
  request=('GET '+path+' HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n'+('Authorization: Bearer '+secret+'\r\n' if secret else '')+'\r\n').encode()
  raw=self.exchange('tcp:'+str(port),request,deadline_seconds=20)
  if b'\r\n\r\n' not in raw:raise UsbAdbError('Controller HTTP response missing')
  header,body=raw.split(b'\r\n\r\n',1);status=int(header.split(b' ')[1])
  if b'transfer-encoding: chunked' in header.lower():
   decoded=bytearray()
   while body:
    line,body=body.split(b'\r\n',1);length=int(line.split(b';')[0],16)
    if not length:break
    decoded.extend(body[:length]);body=body[length+2:]
   body=bytes(decoded)
  if status!=200:raise UsbAdbError('Controller returned HTTP '+str(status))
  return json.loads(body)
