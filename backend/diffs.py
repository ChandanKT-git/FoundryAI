import difflib

MAX_LINES = 3000


def _file_diff(path: str, old, new) -> dict:
    status = "added" if old is None else "removed" if new is None else "modified"
    ol, nl = (old or "").splitlines(), (new or "").splitlines()
    sm = difflib.SequenceMatcher(None, ol, nl, autojunk=False)
    hunks, adds, dels, total = [], 0, 0, 0
    for group in sm.get_grouped_opcodes(3):
        lines = []
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                lines += [{"t": " ", "o": i1 + k + 1, "n": j1 + k + 1, "s": ol[i1 + k]} for k in range(i2 - i1)]
                continue
            if tag in ("replace", "delete"):
                lines += [{"t": "-", "o": k + 1, "n": None, "s": ol[k]} for k in range(i1, i2)]
                dels += i2 - i1
            if tag in ("replace", "insert"):
                lines += [{"t": "+", "o": None, "n": k + 1, "s": nl[k]} for k in range(j1, j2)]
                adds += j2 - j1
        total += len(lines)
        if total <= MAX_LINES:
            hunks.append({"header": f"@@ -{group[0][1] + 1},{group[-1][2] - group[0][1]} "
                                    f"+{group[0][3] + 1},{group[-1][4] - group[0][3]} @@", "lines": lines})
    return {"path": path, "status": status, "additions": adds, "deletions": dels,
            "hunks": hunks, "truncated": total > MAX_LINES}


def diff_files(base: list, target: list) -> dict:
    a = {f["path"]: f["content"] for f in base}
    b = {f["path"]: f["content"] for f in target}
    files = [_file_diff(p, a.get(p), b.get(p)) for p in sorted(set(a) | set(b)) if a.get(p) != b.get(p)]
    return {"files": files, "additions": sum(f["additions"] for f in files),
            "deletions": sum(f["deletions"] for f in files)}
