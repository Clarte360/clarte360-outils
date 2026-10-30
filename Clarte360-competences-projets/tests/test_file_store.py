from __future__ import annotations

from pathlib import Path

from clarte360_cp.repositories.files import ObjectStore, FileRepository


def test_content_addressed_dedup(Session, tmp_path):
    store=ObjectStore(tmp_path/"objects"/"sha256")
    with Session() as s:
        repo=FileRepository(s,store)
        a=repo.register_bytes(b"hello","text/plain")
        b=repo.register_bytes(b"hello","text/plain")
        assert a.file_id==b.file_id
        assert store.verify(a.sha256)
        assert len(list((tmp_path/"objects"/"sha256").rglob(a.sha256)))==1


def test_hash_tampering_detected(Session, tmp_path):
    store=ObjectStore(tmp_path/"objects"/"sha256")
    with Session() as s:
        obj=FileRepository(s,store).register_bytes(b"hello","text/plain")
    path=store.path_for_hash(obj.sha256)
    path.write_bytes(b"tampered")
    assert not store.verify(obj.sha256)
