"""Rules for names the user types: events, subjects, mutually
exclusive groups and folder names.

Names end up in CSV files that LASERcoder and other software read back,
so characters that can be mistaken for structure are refused when a
name is first entered.  Names already stored in a project are left as
they are; callers only check names that are new.
"""

# Besides letters and numbers
ALLOWED_PUNCTUATION = " _-.()"
ALLOWED_DESCRIPTION = "letters, numbers, spaces, and _ - . ( )"

# LASERcoder writes this to mean "no subject" / "no value"
RESERVED_NAME = "NA"

# Characters that cannot be used in a folder name on every platform
_PATH_CHARACTERS = '\\/:*?"<>|'


def _show(char):
    """A character as it can be shown in a message."""
    if char == "\t":
        return "tab"
    if not char.isprintable():
        return f"control character (code {ord(char)})"
    return char


def name_problem(name, what="name"):
    """Why *name* cannot be used as a new event, subject or group name.

    Returns a message for the user, or None when the name is fine.
    *what* names the kind of thing in the message ("event name", ...).
    An empty name is not judged here; callers decide whether a name is
    required.
    """
    name = name.strip()
    if not name:
        return None
    bad = []
    for char in name:
        if not (char.isalnum() or char in ALLOWED_PUNCTUATION):
            shown = _show(char)
            if shown not in bad:
                bad.append(shown)
    if bad:
        return (f"The {what} '{name}' contains characters that are not "
                f"allowed:  {'  '.join(bad)}\n\n"
                f"Use only {ALLOWED_DESCRIPTION}.")
    if name.upper() == RESERVED_NAME:
        return (f"'{name}' cannot be used as a {what}: LASERcoder writes "
                f"{RESERVED_NAME} in its files to mean \"none\".")
    return None


def duplicate_problem(new_names, all_names, what="name"):
    """Message if any of *new_names* matches another entry of
    *all_names* when letter case is ignored, else None.  *all_names*
    lists every entry, the new ones included."""
    counts = {}
    for name in all_names:
        key = name.strip().lower()
        if key:
            counts[key] = counts.get(key, 0) + 1
    for name in new_names:
        if counts.get(name.strip().lower(), 0) > 1:
            return (f"The {what} '{name.strip()}' is used more than once. "
                    "Names that differ only in upper and lower case "
                    "count as the same name.")
    return None


def key_rows_problem(rows, existing_names, existing_groups, what):
    """Check the rows of a key file that is about to be saved.

    *rows* is a list of (name, group) pairs as typed.  Names and groups
    in *existing_names* / *existing_groups* are already stored in the
    file and are accepted unchanged; only new ones are checked.
    Returns a message for the user, or None.
    """
    existing_names = {n.strip() for n in existing_names}
    existing_groups = {g.strip() for g in existing_groups}
    names = [name for name, _group in rows if name.strip()]
    new_names = [n for n in names if n.strip() not in existing_names]
    for name in new_names:
        problem = name_problem(name, f"{what} name")
        if problem:
            return problem
    problem = duplicate_problem(new_names, names, f"{what} name")
    if problem:
        return problem
    for name, group in rows:
        if (name.strip() and group.strip()
                and group.strip() not in existing_groups):
            problem = name_problem(group, "group name")
            if problem:
                return problem
    return None


def folder_name_problem(name):
    """Why *name* cannot be used as a new folder name, or None."""
    name = name.strip()
    bad = []
    for char in name:
        if char in _PATH_CHARACTERS or not char.isprintable():
            shown = _show(char)
            if shown not in bad:
                bad.append(shown)
    if bad:
        return (f"The folder name '{name}' contains characters that are "
                f"not allowed:  {'  '.join(bad)}")
    if name in (".", "..") or name.endswith("."):
        return f"'{name}' cannot be used as a folder name."
    return None


def stored_names_and_groups(path, group_index):
    """Names (first column) and groups (column *group_index*) already
    stored in the key file at *path*; two empty sets if it cannot be
    read or does not exist yet."""
    names, groups = set(), set()
    if not path:
        return names, groups
    try:
        from annotation_store import read_csv_lists
        rows = read_csv_lists(path)
    except (OSError, ValueError):
        return names, groups
    for row in rows:
        if row and row[0].strip():
            names.add(row[0].strip())
        if len(row) > group_index and row[group_index].strip():
            groups.add(row[group_index].strip())
    return names, groups
