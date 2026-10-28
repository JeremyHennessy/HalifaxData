"""Read a retained source capture and write a new local candidate. No network."""
import argparse,json,os,pathlib
from physician_refresh.refresh import assess,MAX_BYTES
def bounded_read(path,cap):
 with path.open("rb") as f:b=f.read(cap+1)
 if len(b)>cap:raise ValueError("Local input exceeds byte cap")
 return b

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
 output=a.output.resolve();source=a.capture.resolve()
 if output.is_relative_to(source) or any(x.lower() in {'public','dist','data','baseline'} for x in output.parts):p.error('Candidate must be outside source/baseline/public data directories')
 try:
  result=assess(bounded_read(source/'payments.body',MAX_BYTES),bounded_read(source/'metadata.body',MAX_BYTES),json.loads(bounded_read(source/'payments.receipt.json',32768)),json.loads(bounded_read(source/'metadata.receipt.json',32768)))
  payload=(json.dumps(result,indent=2,ensure_ascii=False)+'\n').encode();fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
 except (ValueError,KeyError,TypeError,OSError) as e:p.exit(2,f'Candidate withheld: {e}\n')
 print(json.dumps({'candidateRecords':result['diff']['candidateRecords'],'addedKeys':len(result['diff']['addedKeys']),'removedKeys':len(result['diff']['removedKeys']),'changedAmounts':len(result['diff']['changedAmounts']),'publicationAllowed':False}))
if __name__=='__main__':main()
