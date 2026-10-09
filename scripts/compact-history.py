#!/usr/bin/env python3
"""Losslessly retire explicitly selected, closed local snapshot trees.

Only historical scene trees and build-cache payloads are eligible. Findings and
receipts stay at their original paths. Unique bytes live once in ignored storage;
restoration makes independent files, never hard links into the content store.
"""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
STORE = Path('work/retired-storage')
ALLOWED = (Path('work/experiments/scene-runtime'), Path('work/build-cache'))


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def safe_relative(value):
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('Expected a confined relative path')
    return path


def confined(root, value):
    relative = safe_relative(value)
    path = root / relative
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError('Symlink paths are ineligible')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Path escapes workspace')
    return path


def eligible(root, value, protected):
    relative = safe_relative(value)
    if not any(relative.is_relative_to(base) and len(relative.parts) > len(base.parts) + 1
               for base in ALLOWED):
        raise ValueError('Only child snapshot trees and cache payloads are eligible')
    if relative.is_relative_to(ALLOWED[1]) and relative.name != 'payload':
        raise ValueError('Build receipts and APKs are retained in place')
    for item in protected:
        keep = safe_relative(item)
        if relative.is_relative_to(keep) or keep.is_relative_to(relative):
            raise ValueError('Target intersects a protected rollback')
    return confined(root, relative)


def signature(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def entries(tree):
    result = []
    for parent, dirs, files in os.walk(tree, followlinks=False):
        for path in [Path(parent)] + [Path(parent) / name for name in files]:
            info = path.lstat()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError('Only regular files and directories may be retired')
            result.append({'path': path.relative_to(tree).as_posix(),
                           'directory': stat.S_ISDIR(info.st_mode),
                           'mode': stat.S_IMODE(info.st_mode),
                           'mtime_ns': info.st_mtime_ns, 'signature': signature(info)})
        for name in dirs:
            if (Path(parent) / name).is_symlink():
                raise ValueError('Symlink directory is ineligible')
    return sorted(result, key=lambda item: item['path'])


class Storage:
    def __init__(self, root):
        self.root = root
        self.base = confined(root, STORE)
        self.verified = set()
        self.inode_hashes = {}
        self.new_blobs = 0
        self.new_bytes = 0

    def blob(self, checksum):
        if len(checksum) != 64 or any(c not in '0123456789abcdef' for c in checksum):
            raise ValueError('Invalid content checksum')
        return confined(self.root, STORE / 'blobs' / checksum[:2] / (checksum + '.gz'))

    def verify(self, checksum):
        path = self.blob(checksum)
        stamp = (checksum, tuple(signature(path.stat())))
        if stamp not in self.verified:
            with gzip.open(path, 'rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != checksum:
                    raise ValueError('Stored content checksum mismatch')
            self.verified.add(stamp)
        return path

    def save(self, source, record):
        stamp = tuple(record['signature'])
        checksum = self.inode_hashes.get(stamp)
        if checksum is None:
            checksum = digest(source)
            self.inode_hashes[stamp] = checksum
        destination = self.blob(checksum)
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix('.tmp')
            try:
                with source.open('rb') as src, temporary.open('wb') as raw:
                    with gzip.GzipFile(filename='', mode='wb', fileobj=raw,
                                       compresslevel=1, mtime=0) as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
                    raw.flush()
                    os.fsync(raw.fileno())
                temporary.replace(destination)
                self.new_blobs += 1
                self.new_bytes += destination.stat().st_size
            finally:
                temporary.unlink(missing_ok=True)
        self.verify(checksum)
        if signature(source.stat()) != record['signature']:
            raise ValueError('Source changed while archiving; no retirement')
        record['sha256'] = checksum


def retire(root, storage, target, protected):
    tree = eligible(root, target, protected)
    marker = tree.with_name(tree.name + '.retired.json')
    if marker.exists():
        raise ValueError('Target already has a retirement marker')
    if not tree.is_dir():
        raise ValueError('Target must be an existing directory')
    records = entries(tree)
    for record in records:
        if not record['directory']:
            storage.save(tree / record['path'], record)
    identity = hashlib.sha256(target.encode()).hexdigest()
    manifest_path = confined(root, STORE / 'manifests' / (identity + '.json.gz'))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'schema': 1, 'target': target, 'entries': records,
                'reason': 'Superseded expanded copy; all distinct bytes retained'}
    temporary = manifest_path.with_suffix('.tmp')
    with temporary.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as stream:
            stream.write(json.dumps(manifest, separators=(',', ':')).encode())
        raw.flush()
        os.fsync(raw.fileno())
    temporary.replace(manifest_path)
    with gzip.open(manifest_path, 'rt') as stream:
        if json.load(stream) != manifest:
            raise ValueError('Manifest round-trip mismatch')
    # Complete content and path verification precedes the first deletion.
    current = entries(tree)
    expected = [{k: v for k, v in record.items() if k != 'sha256'} for record in records]
    if current != expected:
        raise ValueError('Tree changed during archive; no retirement')
    receipt = {'schema': 1, 'target': target, 'status': 'verified; retirement starting',
               'manifest': manifest_path.relative_to(root).as_posix(),
               'manifest_sha256': digest(manifest_path),
               'files': sum(not r['directory'] for r in records),
               'logical_bytes': sum(r['signature'][2] for r in records if not r['directory']),
               'restore': 'python3 scripts/compact-history.py restore ' + target}
    write_json(marker, receipt)
    shutil.rmtree(tree)
    receipt['status'] = 'retired; all distinct bytes recoverable'
    write_json(marker, receipt)
    return receipt


def restore(root, storage, target, destination=None):
    tree = eligible(root, target, [])
    marker = tree.with_name(tree.name + '.retired.json')
    receipt = json.loads(marker.read_text())
    if receipt.get('recoverable') is False:
        raise ValueError('Obsolete generated output was pruned; rebuild from its archived source')
    manifest_path = confined(root, receipt['manifest'])
    if digest(manifest_path) != receipt['manifest_sha256']:
        raise ValueError('Manifest checksum mismatch')
    with gzip.open(manifest_path, 'rt') as stream:
        manifest = json.load(stream)
    if manifest['schema'] != 1 or manifest['target'] != target:
        raise ValueError('Manifest target/schema mismatch')
    output = confined(root, destination) if destination else tree
    if not output.relative_to(root).is_relative_to('work') or output.exists():
        raise ValueError('Restore requires a new destination under ignored work')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.restore-', dir=output.parent))
    try:
        directories = []
        for record in manifest['entries']:
            path = temporary if record['path'] == '.' else confined(temporary, record['path'])
            if record['directory']:
                path.mkdir(parents=True, exist_ok=True)
                directories.append((path, record))
            else:
                blob = storage.verify(record['sha256'])
                path.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(blob, 'rb') as src, path.open('xb') as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                if digest(path) != record['sha256']:
                    raise ValueError('Restored file checksum mismatch')
                os.chmod(path, record['mode'])
                os.utime(path, ns=(record['mtime_ns'], record['mtime_ns']))
        for path, record in reversed(directories):
            os.chmod(path, record['mode'])
            os.utime(path, ns=(record['mtime_ns'], record['mtime_ns']))
        temporary.rename(output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return {'restored': output.relative_to(root).as_posix(), 'files': receipt['files']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    compact = commands.add_parser('retire')
    compact.add_argument('--plan', required=True)
    compact.add_argument('--apply', action='store_true')
    recover = commands.add_parser('restore')
    recover.add_argument('target')
    recover.add_argument('--destination')
    args = parser.parse_args()
    storage = Storage(ROOT)
    storage.base.mkdir(parents=True, exist_ok=True)
    lock = confined(ROOT, STORE / 'operation.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if args.action == 'restore':
        print(json.dumps(restore(ROOT, storage, args.target, args.destination)))
        return
    plan_path = confined(ROOT, args.plan)
    plan = json.loads(plan_path.read_text())
    if plan.get('schema') != 1 or not plan.get('protected') or not plan.get('targets'):
        raise ValueError('An explicit target list and rollback protection list are required')
    for target in plan['targets']:
        eligible(ROOT, target, plan['protected'])
    if not args.apply:
        print(json.dumps({'validated_targets': len(plan['targets']), 'applied': False}))
        return
    result = {'schema': 1, 'plan_sha256': digest(plan_path), 'started': time.time(),
              'free_before': shutil.disk_usage(ROOT).free, 'retired': [], 'success': False}
    result_path = plan_path.with_name('result.json')
    try:
        for target in plan['targets']:
            receipt = retire(ROOT, storage, target, plan['protected'])
            result['retired'].append(receipt)
            result['free_now'] = shutil.disk_usage(ROOT).free
            write_json(result_path, result)
            print(json.dumps({'retired': target, 'count': len(result['retired']),
                              'free_GiB': round(result['free_now'] / 2**30, 2)}), flush=True)
        result['success'] = True
    finally:
        result.update({'ended': time.time(), 'free_after': shutil.disk_usage(ROOT).free,
                       'new_blobs': storage.new_blobs, 'compressed_bytes': storage.new_bytes})
        write_json(result_path, result)


if __name__ == '__main__':
    main()
