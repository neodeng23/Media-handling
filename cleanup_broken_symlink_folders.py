"""Clean broken symlink files under ROOT_DIR and optionally remove folders.

Rules:
1) Recursively scan ROOT_DIR and all subfolders.
2) Only handle symlink files (not symlink directories).
3) If a symlink target does not exist:
   - If the same folder still has at least one valid symlink file, delete only the broken symlink file.
   - Otherwise, delete the whole folder.

The delete logic uses retry loops to better handle CloudDrive2/WebDAV-like mount delay.
"""

import os
import shutil
import time
from pathlib import Path

# Root path to scan (as requested).
ROOT_DIR = r"F:\P\emby_softlink\J"

# Retry settings for CloudDrive2/WebDAV style paths.
MAX_DELETE_RETRIES = 5
RETRY_DELAY_SEC = 1.5


def normalize_path_str(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def is_existing_dir(path: Path) -> bool:
    try:
        return path.exists() and path.is_dir()
    except Exception:
        return False


def resolve_symlink_target(link_path: Path):
    """Return absolute target path for link_path; return None if unreadable."""
    try:
        linked_target = os.readlink(str(link_path))
    except Exception:
        return None

    if not os.path.isabs(linked_target):
        linked_target = os.path.join(str(link_path.parent), linked_target)

    return Path(os.path.abspath(linked_target))


def is_symlink_target_valid(link_path: Path):
    """Return (is_valid, target_path_or_none)."""
    target_path = resolve_symlink_target(link_path)
    if target_path is None:
        return False, None

    try:
        return target_path.exists(), target_path
    except Exception:
        return False, target_path


def delete_symlink_file_with_retry(link_path: Path) -> bool:
    for attempt in range(1, MAX_DELETE_RETRIES + 1):
        try:
            if not link_path.exists() and not link_path.is_symlink():
                return True
        except Exception:
            # If metadata read fails, continue to delete attempt.
            pass

        try:
            link_path.unlink()
        except FileNotFoundError:
            return True
        except Exception as exc:
            print(f"[WARN] Failed to delete link ({attempt}/{MAX_DELETE_RETRIES}): {link_path}, reason: {exc}")

        try:
            if not link_path.exists() and not link_path.is_symlink():
                return True
        except Exception:
            return True

        if attempt < MAX_DELETE_RETRIES:
            time.sleep(RETRY_DELAY_SEC)

    return False


def delete_folder_with_retry(folder_path: Path) -> bool:
    for attempt in range(1, MAX_DELETE_RETRIES + 1):
        if not folder_path.exists():
            return True

        try:
            shutil.rmtree(str(folder_path))
        except FileNotFoundError:
            return True
        except Exception as exc:
            print(f"[WARN] Failed to delete folder ({attempt}/{MAX_DELETE_RETRIES}): {folder_path}, reason: {exc}")

        if not folder_path.exists():
            return True

        if attempt < MAX_DELETE_RETRIES:
            time.sleep(RETRY_DELAY_SEC)

    return False


def collect_symlink_files(folder: Path, files):
    result = []
    for file_name in files:
        file_path = folder / file_name
        try:
            if file_path.is_symlink():
                result.append(file_path)
        except Exception as exc:
            print(f"[WARN] Failed to inspect file: {file_path}, reason: {exc}")
    return result


def process_one_folder(current_folder: Path, files, root_norm: str, stats: dict):
    symlink_files = collect_symlink_files(current_folder, files)
    if not symlink_files:
        return

    stats["symlink_files_scanned"] += len(symlink_files)

    valid_links = []
    broken_links = []
    for link_path in symlink_files:
        is_valid, target_path = is_symlink_target_valid(link_path)
        if is_valid:
            valid_links.append((link_path, target_path))
        else:
            broken_links.append((link_path, target_path))

    if not broken_links:
        return

    stats["broken_symlink_files"] += len(broken_links)

    if valid_links:
        stats["folders_kept_due_to_valid_symlink"] += 1
        print(
            f"[INFO] Keep folder (has valid symlink): {current_folder} "
            f"(valid={len(valid_links)}, broken={len(broken_links)})"
        )

        for broken_link, target_path in broken_links:
            target_str = str(target_path) if target_path else "<unknown>"
            print(f"[INFO] Delete broken symlink only: {broken_link} -> {target_str}")
            if delete_symlink_file_with_retry(broken_link):
                stats["symlink_files_deleted"] += 1
                print(f"[DELETED-LINK] {broken_link}")
            else:
                stats["symlink_delete_failed"] += 1
                print(f"[FAILED-LINK] {broken_link}")
        return

    # No valid symlink in this folder, delete whole folder (except root).
    if normalize_path_str(current_folder) == root_norm:
        print(f"[INFO] Root folder has only broken symlink(s); root will not be deleted: {current_folder}")
        for broken_link, target_path in broken_links:
            target_str = str(target_path) if target_path else "<unknown>"
            print(f"[INFO] Delete broken symlink in root: {broken_link} -> {target_str}")
            if delete_symlink_file_with_retry(broken_link):
                stats["symlink_files_deleted"] += 1
                print(f"[DELETED-LINK] {broken_link}")
            else:
                stats["symlink_delete_failed"] += 1
                print(f"[FAILED-LINK] {broken_link}")
        return

    print(f"[INFO] Delete folder (all symlink files in folder are broken): {current_folder}")
    for broken_link, target_path in broken_links:
        target_str = str(target_path) if target_path else "<unknown>"
        print(f"[INFO] Broken symlink in folder: {broken_link} -> {target_str}")

    if delete_folder_with_retry(current_folder):
        stats["folders_deleted"] += 1
        stats["symlink_files_deleted"] += len(broken_links)
        print(f"[DELETED-FOLDER] {current_folder}")
    else:
        stats["folder_delete_failed"] += 1
        print(f"[FAILED-FOLDER] {current_folder}")
        print("[INFO] Folder deletion failed, fallback to deleting broken symlink files only.")
        for broken_link, target_path in broken_links:
            target_str = str(target_path) if target_path else "<unknown>"
            print(f"[INFO] Fallback delete broken symlink: {broken_link} -> {target_str}")
            if delete_symlink_file_with_retry(broken_link):
                stats["symlink_files_deleted"] += 1
                print(f"[DELETED-LINK] {broken_link}")
            else:
                stats["symlink_delete_failed"] += 1
                print(f"[FAILED-LINK] {broken_link}")


def process_directory_tree(scan_root: Path, root_norm: str, stats: dict):
    # Bottom-up walk makes folder deletion safer during traversal.
    for current_root, _dirs, files in os.walk(str(scan_root), topdown=False, followlinks=False):
        current_folder = Path(current_root)

        # Cloud mounts may update slowly; skip already-missing folders.
        if not current_folder.exists():
            continue

        process_one_folder(current_folder, files, root_norm, stats)


def process_top_level_non_dir(item: Path, stats: dict):
    # Only process symlink files at root-level non-dir entries.
    try:
        if not item.is_symlink():
            return
    except Exception as exc:
        print(f"[WARN] Failed to inspect top-level file: {item}, reason: {exc}")
        return

    stats["symlink_files_scanned"] += 1
    is_valid, target_path = is_symlink_target_valid(item)
    if is_valid:
        return

    stats["broken_symlink_files"] += 1
    target_str = str(target_path) if target_path else "<unknown>"
    print(f"[INFO] Delete broken symlink in root: {item} -> {target_str}")
    if delete_symlink_file_with_retry(item):
        stats["symlink_files_deleted"] += 1
        print(f"[DELETED-LINK] {item}")
    else:
        stats["symlink_delete_failed"] += 1
        print(f"[FAILED-LINK] {item}")


def make_delta(before: dict, after: dict):
    return {k: after[k] - before[k] for k in after.keys()}


def main():
    root = Path(os.path.abspath(ROOT_DIR))

    if not is_existing_dir(root):
        print(f"[ERROR] Root folder not found or invalid: {root}")
        return

    print(f"[INFO] Start scanning: {root}")

    stats = {
        "symlink_files_scanned": 0,
        "broken_symlink_files": 0,
        "symlink_files_deleted": 0,
        "folders_deleted": 0,
        "symlink_delete_failed": 0,
        "folder_delete_failed": 0,
        "folders_kept_due_to_valid_symlink": 0,
    }

    root_norm = normalize_path_str(root)

    top_level_items = sorted(list(root.iterdir()), key=lambda p: str(p).lower())
    total_top_level = len(top_level_items)
    print(f"[INFO] Top-level items: {total_top_level}")

    for index, item in enumerate(top_level_items, start=1):
        before = dict(stats)

        try:
            # Skip symlink directories at top level.
            if item.is_dir():
                if item.is_symlink():
                    print(f"[INFO] Skip top-level symlink directory: {item}")
                else:
                    process_directory_tree(item, root_norm, stats)
            else:
                process_top_level_non_dir(item, stats)
        except Exception as exc:
            print(f"[WARN] Failed to process top-level item: {item}, reason: {exc}")

        delta = make_delta(before, stats)
        print(
            f"[TOP-DONE] ({index}/{total_top_level}) {item} | "
            f"scan={delta['symlink_files_scanned']}, "
            f"broken={delta['broken_symlink_files']}, "
            f"del_link={delta['symlink_files_deleted']}, "
            f"del_dir={delta['folders_deleted']}, "
            f"fail_link={delta['symlink_delete_failed']}, "
            f"fail_dir={delta['folder_delete_failed']}"
        )

    print("\n=== Done ===")
    print(f"Scanned symlink files: {stats['symlink_files_scanned']}")
    print(f"Broken symlink files: {stats['broken_symlink_files']}")
    print(f"Deleted symlink files: {stats['symlink_files_deleted']}")
    print(f"Deleted folders: {stats['folders_deleted']}")
    print(f"Failed symlink deletions: {stats['symlink_delete_failed']}")
    print(f"Failed folder deletions: {stats['folder_delete_failed']}")
    print(f"Folders kept due to valid symlink: {stats['folders_kept_due_to_valid_symlink']}")


if __name__ == "__main__":
    main()
