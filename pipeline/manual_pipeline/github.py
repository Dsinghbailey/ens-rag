import os
import subprocess
import time
import logging
from typing import List, Dict


# --- GitHub Interaction ---
def fetch_repo_files(
    repo_url: str, folders: List[str], token: str, customer_id: int
) -> Dict[str, str]:
    """Clones repo temporarily and reads markdown files from specified folders."""
    # Using Git CLI - ensure git is installed in the Render Worker environment
    # Alternative: Use GitHub API via PyGithub/githubkit for more robustness & less disk I/O
    logging.info(f"[{customer_id}] Fetching files from {repo_url}, folders: {folders}")
    repo_name = repo_url.split("/")[-1]
    # Use a customer-specific temp dir if needed
    # Ensure the base tmp directory exists
    base_tmp_dir = "./tmp_clones"
    os.makedirs(base_tmp_dir, exist_ok=True)
    clone_dir = os.path.join(
        base_tmp_dir, f"clone_{customer_id}_{repo_name}_{int(time.time())}"
    )

    # Simple cleanup of potentially old directories in base_tmp_dir (optional)
    # Be cautious with automated rm -rf
    # Example: Find dirs older than 1 day
    # find ./tmp_clones -maxdepth 1 -type d -mtime +1 -exec rm -rf {} \;

    if os.path.exists(clone_dir):
        logging.warning(
            f"[{customer_id}] Temporary clone directory already exists, removing: {clone_dir}"
        )
        subprocess.run(["rm", "-rf", clone_dir], check=False)  # Best effort remove

    # Use token for private repos via HTTPS
    auth_repo_url = f"https://oauth2:{token}@github.com/{repo_url}.git"
    try:
        # Clone only necessary history (--depth 1) and maybe specific branches if needed
        # Consider sparse checkout if only specific folders are *always* needed
        git_command = [
            "git",
            "clone",
            "--depth",
            "1",
            "--no-tags",
            "--quiet",
            auth_repo_url,
            clone_dir,
        ]
        logging.info(f"[{customer_id}] Running git clone into {clone_dir}...")
        result = subprocess.run(
            git_command, check=True, capture_output=True, text=True, timeout=300
        )  # 5 min timeout
        logging.info(f"[{customer_id}] Git clone completed.")
    except subprocess.TimeoutExpired:
        logging.error(f"[{customer_id}] Git clone timed out for {repo_url}")
        subprocess.run(["rm", "-rf", clone_dir], check=False)
        return {}
    except subprocess.CalledProcessError as e:
        logging.error(f"[{customer_id}] Error cloning {repo_url}: {e.stderr}")
        subprocess.run(["rm", "-rf", clone_dir], check=False)
        return {}
    except Exception as e:
        logging.error(f"[{customer_id}] Unexpected error during clone setup: {e}")
        if os.path.exists(clone_dir):
            subprocess.run(["rm", "-rf", clone_dir], check=False)
        return {}

    markdown_files = {}
    try:
        for folder in folders:
            # Ensure folder path is relative and safe
            safe_folder = os.path.normpath(os.path.join("./", folder))
            if safe_folder.startswith(("..", "/")):
                logging.warning(
                    f"[{customer_id}] Skipping potentially unsafe folder path: {folder}"
                )
                continue

            scan_path = os.path.join(clone_dir, safe_folder)
            if not os.path.exists(scan_path) or not os.path.isdir(scan_path):
                logging.warning(
                    f"[{customer_id}] Specified folder not found or not a directory: {folder} in {repo_url} (resolved: {scan_path})"
                )
                continue

            logging.info(f"[{customer_id}] Scanning {scan_path}...")
            for root, _, files in os.walk(scan_path):
                for file in files:
                    if file.lower().endswith((".md", ".mdx")):  # Support mdx
                        file_path = os.path.join(root, file)
                        # Use relative path from repo root for consistency
                        relative_path = os.path.relpath(file_path, clone_dir)
                        # Construct a source URL (e.g., link to GitHub file view)
                        # TODO: Determine default branch dynamically instead of assuming 'main'
                        source_identifier = (
                            f"https://github.com/{repo_url}/blob/main/{relative_path}"
                        )
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                markdown_files[source_identifier] = f.read()
                        except UnicodeDecodeError:
                            try:
                                with open(file_path, "r", encoding="latin-1") as f:
                                    logging.warning(
                                        f"[{customer_id}] File {relative_path} read with latin-1 encoding."
                                    )
                                    markdown_files[source_identifier] = f.read()
                            except Exception as e_read:
                                logging.error(
                                    f"[{customer_id}] Error reading file {relative_path} with fallback encoding: {e_read}"
                                )
                        except Exception as e:
                            logging.error(
                                f"[{customer_id}] Error reading file {relative_path}: {e}"
                            )
    finally:
        # Ensure cleanup happens
        logging.info(f"[{customer_id}] Cleaning up temporary directory: {clone_dir}")
        subprocess.run(["rm", "-rf", clone_dir], check=False)

    logging.info(
        f"[{customer_id}] Found {len(markdown_files)} markdown files from {repo_url}."
    )
    return markdown_files
