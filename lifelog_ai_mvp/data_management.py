import io
import json
import sqlite3
import zipfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def _connect(db_path):
    connection = sqlite3.connect(db_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _asset_path(assets_root, user_id, stored_name):
    user_dir = (Path(assets_root) / str(user_id)).resolve()
    path = (user_dir / stored_name).resolve()
    if path.parent != user_dir:
        raise ValueError("Invalid asset path in stored metadata.")
    return path


def update_memory(
    db_path, user_id, memory_id, title, tags, memory_date, source_text, result
):
    with _connect(db_path) as connection:
        cursor = connection.execute(
            "UPDATE memories SET title = ?, tags = ?, memory_date = ?, "
            "source_text = ?, result_json = ? WHERE id = ? AND user_id = ?",
            (
                title.strip() or "Untitled memory",
                tags.strip(),
                memory_date,
                source_text.strip(),
                json.dumps(result, ensure_ascii=False),
                memory_id,
                user_id,
            ),
        )
        connection.commit()
        return cursor.rowcount == 1


def _remove_asset_files(paths):
    failures = []
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except OSError as error:
            failures.append(f"{path.name}: {error}")
    if failures:
        raise OSError(
            "Database records were deleted, but some stored files could not be "
            "removed: " + "; ".join(failures)
        )


def delete_memory(db_path, assets_root, user_id, memory_id):
    with _connect(db_path) as connection:
        memory = connection.execute(
            "SELECT id FROM memories WHERE id = ? AND user_id = ?",
            (memory_id, user_id),
        ).fetchone()
        if not memory:
            return False
        stored_names = connection.execute(
            "SELECT stored_name FROM assets WHERE memory_id = ? AND user_id = ?",
            (memory_id, user_id),
        ).fetchall()
        paths = [
            _asset_path(assets_root, user_id, row[0]) for row in stored_names
        ]
        connection.execute(
            "DELETE FROM reminder_deliveries WHERE task_id IN "
            "(SELECT id FROM tasks WHERE memory_id = ? AND user_id = ?)",
            (memory_id, user_id),
        )
        connection.execute(
            "DELETE FROM tasks WHERE memory_id = ? AND user_id = ?",
            (memory_id, user_id),
        )
        connection.execute(
            "DELETE FROM assets WHERE memory_id = ? AND user_id = ?",
            (memory_id, user_id),
        )
        connection.execute(
            "DELETE FROM memories WHERE id = ? AND user_id = ?",
            (memory_id, user_id),
        )
        connection.commit()
    _remove_asset_files(paths)
    return True


def export_user_archive(db_path, assets_root, user_id):
    with _connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        user = connection.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            raise LookupError("The account no longer exists.")
        profile_row = connection.execute(
            "SELECT display_name, writing_style, journal_tone, interests, reminder_time "
            "FROM profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        memories = [
            dict(row)
            for row in connection.execute(
                "SELECT id, created_at, source_text, mode, result_json, title, tags, "
                "memory_date FROM memories WHERE user_id = ? ORDER BY id",
                (user_id,),
            ).fetchall()
        ]
        tasks = [
            dict(row)
            for row in connection.execute(
                "SELECT id, memory_id, title, completed, created_at, due_date, "
                "priority, reminder_enabled FROM tasks WHERE user_id = ? ORDER BY id",
                (user_id,),
            ).fetchall()
        ]
        assets = [
            dict(row)
            for row in connection.execute(
                "SELECT id, memory_id, original_name, stored_name, asset_type, "
                "size_bytes, status, extracted_text, created_at FROM assets "
                "WHERE user_id = ? ORDER BY id",
                (user_id,),
            ).fetchall()
        ]

    profile = dict(profile_row) if profile_row else None
    for memory in memories:
        memory["result"] = json.loads(memory.pop("result_json"))

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for asset in assets:
            path = _asset_path(assets_root, user_id, asset["stored_name"])
            if not path.is_file():
                raise FileNotFoundError(
                    f"Stored file for attachment {asset['id']} is missing."
                )
            filename = Path(asset["original_name"]).name or "attachment"
            archive_path = f"assets/{asset['id']}_{filename}"
            bundle.write(path, archive_path)
            asset["archive_path"] = archive_path
            asset.pop("stored_name")

        payload = {
            "account": dict(user),
            "profile": profile,
            "memories": memories,
            "tasks": tasks,
            "assets": assets,
        }
        bundle.writestr(
            "lifelog-export.json",
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
    return archive.getvalue()


def delete_user_account(db_path, assets_root, user_id):
    with _connect(db_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not exists:
            return False
        stored_names = connection.execute(
            "SELECT stored_name FROM assets WHERE user_id = ?", (user_id,)
        ).fetchall()
        paths = [
            _asset_path(assets_root, user_id, row[0]) for row in stored_names
        ]
        connection.execute(
            "DELETE FROM reminder_deliveries WHERE task_id IN "
            "(SELECT id FROM tasks WHERE user_id = ?)",
            (user_id,),
        )
        connection.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM assets WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        connection.commit()
    _remove_asset_files(paths)
    return True
