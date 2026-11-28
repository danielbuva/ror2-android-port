"""Prepare and publish the checked-out topic through the lab's normal checks."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from source_pins import build_plan


ROOT = Path(__file__).resolve().parents[2]
MAIN = "refs/remotes/origin/main"
PR_FIELDS = "number,url,headRefOid,isCrossRepository"


def pr_for_tip(run, branch, tip):
    pulls = json.loads(run("gh", "pr", "list", "--state", "open", "--base", "main", "--head", branch, "--json", PR_FIELDS, output=True))
    pulls = [pull for pull in pulls if not pull["isCrossRepository"]]
    if pulls:
        (pull,) = pulls
    else:
        url = run("gh", "pr", "create", "--base", "main", "--head", branch, "--fill-first", output=True)
        pull = json.loads(run("gh", "pr", "view", url, "--json", PR_FIELDS, output=True))
    if pull["isCrossRepository"] or pull["headRefOid"] != tip:
        raise ValueError(f"PR #{pull['number']} does not point to the published commit {tip}")
    print(pull["url"])
    print(f"AUTOMERGE {pull['number']}")


def publish(root, open_pr):
    def run(*args, output=False):
        result = subprocess.run(args, cwd=root, check=True, text=True, stdout=subprocess.PIPE if output else None)
        return result.stdout.strip() if output else None

    ref = run("git", "symbolic-ref", "--quiet", "HEAD", output=True)
    if not ref.startswith("refs/heads/") or ref in {"refs/heads/main", "refs/heads/master"}:
        raise ValueError("check out a topic branch before publishing")
    branch = ref.removeprefix("refs/heads/")
    if run("git", "status", "--porcelain", "--untracked-files=no", output=True):
        raise ValueError("commit or stash tracked changes before publishing")
    for role in ("AUTHOR", "COMMITTER"):
        ident = run("git", "var", f"GIT_{role}_IDENT", output=True)
        if not ident.split(" <", 1)[1].split(">", 1)[0].endswith("@users.noreply.github.com"):
            raise ValueError(f"configure a GitHub noreply {role.lower()} email before publishing")

    run("git", "fetch", "--prune", "origin")
    run("git", "merge", "--no-edit", MAIN)
    main = run("git", "rev-parse", MAIN, output=True)
    tip = run("git", "rev-parse", ref, output=True)
    tracking_ref = f"refs/remotes/origin/{branch}"
    refs = run("git", "for-each-ref", "--format=%(refname) %(objectname)", tracking_ref, output=True)
    remote_tip = dict(line.split() for line in refs.splitlines()).get(tracking_ref)
    if remote_tip and subprocess.run(["git", "merge-base", "--is-ancestor", remote_tip, tip], cwd=root).returncode != 0:
        raise ValueError(f"integrate origin/{branch} before publishing")

    run(sys.executable, "-B", "scripts/journal-pre-push.py", "--prepare", ref, tip, ref)
    tip = run("git", "rev-parse", ref, output=True)
    plan = build_plan(root, tip, remote_tip or main)
    plan.report(show_external=False)
    if plan.issues:
        raise ValueError("resolve the source pin errors before publishing")
    if plan.outputs:
        if not plan.write(root, tip, ref):
            raise ValueError("could not refresh the tracked-source pins")
        paths = sorted(plan.outputs)
        run("git", "add", "--", *paths)
        run(sys.executable, "-B", "scripts/audit-public.py")
        run("git", "commit", "--only", "-m", "chore(lab): refresh tracked-source pins", "--", *paths)
        tip = run("git", "rev-parse", ref, output=True)

    run("git", "-c", "core.hooksPath=scripts/git-hooks", "push", "--set-upstream", "origin", f"{ref}:{ref}")
    remote = run("git", "ls-remote", "--refs", "origin", ref, output=True)
    if remote != f"{tip}\t{ref}":
        raise ValueError(f"origin/{branch} does not point to the prepared commit {tip}")
    if open_pr:
        pr_for_tip(run, branch, tip)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="./dev publish", description="Current host workflow to repair and push the checked-out topic branch.")
    parser.add_argument("--pr", action="store_true", help="open or find the PR to main and print its merge bot registration line")
    args = parser.parse_args(argv)
    try:
        publish(ROOT, args.pr)
    except subprocess.CalledProcessError as error:
        command = "git push" if error.cmd[:2] == ("git", "-c") else " ".join(map(str, error.cmd[:2]))
        print(f"Publish stopped at {command} (exit {error.returncode}).", file=sys.stderr)
        return 1
    except (KeyError, OSError, ValueError) as error:
        print(f"Publish stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
