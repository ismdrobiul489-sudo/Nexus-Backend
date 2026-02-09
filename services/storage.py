from huggingface_hub import HfApi, upload_file, delete_file, list_repo_files
import os

class StorageService:
    @staticmethod
    def list_files(token: str, repo: str, path: str = None):
        api = HfApi(token=token)
        # Use list_repo_tree to get full metadata (size, type)
        tree = api.list_repo_tree(
            repo_id=repo,
            repo_type="dataset",
            path_in_repo=path,
            recursive=False
        )
        
        results = []
        for entry in tree:
            results.append({
                "name": os.path.basename(entry.path),
                "path": entry.path,
                "type": "directory" if hasattr(entry, "type") and entry.type == "directory" else "file",
                "size": getattr(entry, "size", 0),
                "last_modified": getattr(entry, "last_modified", None)
            })
        return results

    @staticmethod
    def create_folder(token: str, repo: str, folder_path: str):
        api = HfApi(token=token)
        # 1:1 Parity: Create .gitkeep to simulate folder
        api.upload_file(
            path_or_fileobj=b"",
            path_in_repo=f"{folder_path}/.gitkeep",
            repo_id=repo,
            repo_type="dataset",
            commit_message=f"Create folder {folder_path}"
        )
        return True

    @staticmethod
    def get_repo_info(token: str, repo: str):
        """Fetches repository info similar to getRepoInfo in hfStorageService.ts"""
        import httpx
        url = f"https://huggingface.co/api/datasets/{repo}"
        headers = {"Authorization": f"Bearer {token}"}
        try:
            with httpx.Client() as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "id": data.get("id"),
                        "private": data.get("private", False),
                        "lastModified": data.get("lastModified", "")
                    }
        except:
            pass
        return None

    @staticmethod
    def upload(token: str, repo: str, file_path: str, path_in_repo: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        api = HfApi(token=token)
        api.upload_file(
            path_or_fileobj=file_path,
            path_in_repo=path_in_repo,
            repo_id=repo,
            repo_type="dataset",
            commit_message=f"Upload {os.path.basename(file_path)}"
        )
        return True

    @staticmethod
    def delete(token: str, repo: str, path_in_repo: str):
        api = HfApi(token=token)
        api.delete_file(
            path_in_repo=path_in_repo,
            repo_id=repo,
            repo_type="dataset",
            commit_message=f"Delete {path_in_repo}"
        )
        return True
        
    @staticmethod
    def get_url(repo: str, path_in_repo: str) -> str:
        return f"https://huggingface.co/datasets/{repo}/resolve/main/{path_in_repo}"
