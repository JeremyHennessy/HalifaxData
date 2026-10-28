"""Explicit offline CLI. Never writes application data or public build output."""
import argparse, json, os, pathlib, sys
from .adapters import build
from .engine import run

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=pathlib.Path, help='Directory containing the three pinned admitted JSON snapshots and receipts')
    parser.add_argument('--output', required=True, type=pathlib.Path, help='New private local report path; existing files are never replaced')
    args=parser.parse_args(argv)
    output=args.output.resolve()
    if any(p.lower() in {'public','dist','data','fixtures'} for p in output.parts):
        parser.error('Output must be outside public/dist/data/fixtures directories')
    if output.is_relative_to(args.input.resolve()):
        parser.error('Output must be outside the input snapshot directory')
    try:
        result=run(build(args.input))
        payload=(json.dumps(result,indent=2)+'\n').encode()
        fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(payload);stream.flush();os.fsync(stream.fileno())
    except (ValueError,KeyError,TypeError,OSError) as exc:
        parser.exit(2,f'No successful report: {exc}\n')
    print(json.dumps(result['counts'],sort_keys=True))
    return 0

if __name__=='__main__':sys.exit(main())
