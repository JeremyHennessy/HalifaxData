"""Pure bounded REP matching; not source-access authorization or transport policy."""
from dataclasses import dataclass
import hashlib,re,urllib.parse
MAX_POLICY=512000
MAX_TARGET=8192
MAX_STEPS=2000000
UNRESERVED=set(b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~')
class PolicyHold(ValueError):pass

def require(ok,message):
 if not ok:raise PolicyHold(message)

def octets(text,pattern=False):
 """Keep encoded reserved octets distinct; decode encoded unreserved octets only."""
 out=[];i=0
 while i<len(text):
  char=text[i]
  if char=='%':
   require(i+2<len(text) and re.fullmatch('[0-9a-fA-F]{2}',text[i+1:i+3]),'Malformed percent escape')
   n=int(text[i+1:i+3],16);out.extend(chr(n) if n in UNRESERVED else '%'+format(n,'02X'));i+=3;continue
  if pattern and char=='*':out.append(None)
  elif char in '*$':out.extend('%'+format(ord(char),'02X'))
  elif ord(char)>=128 or ord(char) not in UNRESERVED and char not in "/:?[]@!&'()+,;=":
   out.extend(''.join('%'+format(n,'02X') for n in char.encode('utf-8')))
  else:
   require(32<ord(char)<127,'Control character in URI pattern');out.append(char)
  i+=1
 return tuple(out)

@dataclass(frozen=True)
class Rule:
 allow:bool
 pattern:str
 atoms:tuple
 end:bool
 specificity:int
 line:int

@dataclass
class Group:
 agents:list
 rules:list
 delay:float=0
 has_directive:bool=False

def parse(body):
 require(type(body) is bytes and len(body)<=MAX_POLICY,'Policy exceeds bounded parser limit')
 try:text=body.decode('utf-8-sig',errors='strict')
 except UnicodeError as e:raise PolicyHold('Policy is not valid UTF-8') from e
 require(not any(ord(c)<32 and c not in '\r\n\t' or ord(c)==127 for c in text) and '<html' not in text.lower() and '<!doctype' not in text.lower(),'Policy is not plain robots text')
 groups=[];group=None
 for lineno,raw in enumerate(text.replace('\r\n','\n').replace('\r','\n').split('\n'),1):
  line=raw.split('#',1)[0].strip(' \t')
  if not line:continue
  require(len(line)<=8192 and ':' in line,'Malformed or oversized policy line')
  key,value=(s.strip(' \t') for s in line.split(':',1));key=key.lower()
  require(key in {'user-agent','allow','disallow','sitemap','crawl-delay'},'Unsupported directive requires review')
  if key=='sitemap':
   require(bool(value),'Empty Sitemap');continue
  if key=='user-agent':
   require(value=='*' or bool(re.fullmatch('[A-Za-z_-]+',value)),'Invalid product token')
   if group is None or group.has_directive:group=Group([],[]);groups.append(group)
   group.agents.append(value.lower());continue
  require(group is not None,'Rule before first user-agent requires review')
  group.has_directive=True
  if key=='crawl-delay':
   require(bool(re.fullmatch(r'\d+(?:\.\d+)?',value)) and float(value)<=3600,'Unsupported crawl-delay');group.delay=max(group.delay,float(value));continue
  if not value:continue
  # RFC9309 section5.1 explicitly includes leading-wildcard *.gif$.
  require(value.startswith(('/', '*')) and not any(c.isspace() for c in value),'Malformed relative or whitespace path rule')
  end=value.endswith('$');pattern=value[:-1] if end else value
  require('$' not in pattern,'Literal dollar in pattern must be percent-encoded')
  raw_atoms=octets(pattern,pattern=True);normalized=[]
  for atom in raw_atoms:
   if atom is None and normalized and normalized[-1] is None:continue
   normalized.append(atom)
  # Trailing wildcard is a redundant prefix match, including when followed by $.
  if normalized and normalized[-1] is None:normalized.pop();end=False
  atoms=tuple(normalized)
  specificity=len(atoms)+int(end)
  group.rules.append(Rule(key=='allow',value,atoms,end,specificity,lineno))
 return groups

def match(rule,target,budget):
 """Bounded NFA; wildcard can consume zero or more normalized octets."""
 active={0};atoms=rule.atoms
 def closure(states):
  states=set(states);stack=list(states)
  while stack:
   pos=stack.pop();budget[0]-=1
   require(budget[0]>=0,'Matching work limit requires review')
   if pos<len(atoms) and atoms[pos] is None and pos+1 not in states:states.add(pos+1);stack.append(pos+1)
  return states
 active=closure(active)
 if not rule.end and len(atoms) in active:return True
 for atom in target:
  nextstates=set()
  for pos in active:
   budget[0]-=1;require(budget[0]>=0,'Matching work limit requires review')
   if pos<len(atoms):
    if atoms[pos] is None:nextstates.add(pos)
    elif atoms[pos]==atom:nextstates.add(pos+1)
  active=closure(nextstates)
  if not active:return False
  if not rule.end and len(atoms) in active:return True
 return len(atoms) in active

def decide(body,url,product_token):
 """Return allow/disallow/review_required; existing source holds always remain external."""
 result={'schemaVersion':'robots-match-decision-v1','policySha256':hashlib.sha256(body).hexdigest() if type(body) is bytes else None,'url':url,'productToken':product_token,'accessAuthorized':False,'transportOrExistingHoldChanged':False}
 try:
  require(isinstance(product_token,str) and bool(re.fullmatch('[A-Za-z_-]+',product_token)),'Supply exact valid product token, not full HTTP header')
  require(isinstance(url,str) and len(url)<=MAX_TARGET and not any(ord(c)<32 or ord(c)==127 for c in url),'Invalid or oversized target')
  p=urllib.parse.urlsplit(url);require(p.scheme in ('http','https') and p.netloc and not p.username and not p.password and not p.fragment,'Unsupported target URL')
  groups=parse(body);token=product_token.lower();selected=[g for g in groups if token in g.agents]
  selection='exact_product_token'
  if not selected:selected=[g for g in groups if '*' in g.agents];selection='wildcard_fallback'
  if not selected:selection='no_applicable_group'
  path=(p.path or '/')+('?' + p.query if p.query else '');target=octets(path);budget=[MAX_STEPS]
  matches=[r for g in selected for r in g.rules if match(r,target,budget)]
  if p.path=='/robots.txt' and not p.query:matches=[]
  best=max((r.specificity for r in matches),default=None)
  winners=[r for r in matches if r.specificity==best]
  allowed=not winners or any(r.allow for r in winners)
  return dict(result,status='allow' if allowed else 'disallow',selection=selection,applicableGroups=len(selected),crawlDelaySeconds=max((g.delay for g in selected),default=0),matchedRules=[{'line':r.line,'pattern':r.pattern,'allow':r.allow,'specificityOctets':r.specificity,'normalizedPattern':''.join('*' if a is None else a for a in r.atoms)+('$' if r.end else '')} for r in winners],reason='Most specific matching rule; Allow wins equivalent-specificity ties' if winners else 'No matching rule',remainingWorkBudget=budget[0])
 except (PolicyHold,ValueError,UnicodeError) as e:return dict(result,status='review_required',reason=str(e))
