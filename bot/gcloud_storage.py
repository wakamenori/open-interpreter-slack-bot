import fnmatch
import os
from typing import List

from google.cloud import storage


def get_ignore_patterns(ignore_file_path):
    """
    Get ignore patterns from .gitignore file
    :param ignore_file_path: path of .gitignore file
    :return: list of ignore patterns
    """
    if os.path.exists(ignore_file_path):
        with open(ignore_file_path, "r") as f:
            return f.read().splitlines()
    else:
        return []


def get_bucket_name(user_id: str) -> str:
    """
    Get GCS bucket name from user_id
    :param user_id: user id
    :return: bucket name
    """
    return f"open-interpreter-{user_id}".lower()


def download_files_from_bucket(bucket_name: str, destination_dir_path: str, blob_prefix: str) -> List[str]:
    """
    Download files from GCS bucket to cloud run
    :param bucket_name: bucket name to download
    :param destination_dir_path: directory path to save files
    :param blob_prefix: prefix of blob to download
    """
    # Initialize the Cloud Storage client
    storage_client = storage.Client()

    if not os.path.exists(destination_dir_path):
        os.makedirs(destination_dir_path)

    # Check if the bucket exists
    if not storage_client.lookup_bucket(bucket_name):
        storage_client.create_bucket(bucket_name)
        return []

    # Get the bucket
    bucket = storage_client.get_bucket(bucket_name)

    file_paths = []

    # Loop through the blobs (files) and download them
    for blob in bucket.list_blobs(prefix=blob_prefix):
        file_name = os.path.basename(blob.name)
        destination_file_path = os.path.join(destination_dir_path, file_name)
        blob.download_to_filename(destination_file_path)
        file_paths.append(destination_file_path)
    return file_paths


def upload_files_to_bucket(local_directory_path: str, bucket_name: str, blob_prefix: str):
    """
    Upload files from cloud run to GCS bucket
    :param local_directory_path: directory path to upload files in cloud run
    :param bucket_name: bucket name to upload
    :param blob_prefix: prefix of blob to upload
    """
    # Initialize the Cloud Storage client
    storage_client = storage.Client()

    # Get the bucket
    bucket = storage_client.get_bucket(bucket_name)

    # Check if the directory exists
    if not os.path.exists(local_directory_path):
        return

    ignore_patterns = get_ignore_patterns("../.gitignore")

    # Loop through each file in the temporary directory
    for root, _, files in os.walk(local_directory_path):
        for filename in files:
            if any(fnmatch.fnmatch(filename, pattern) for pattern in ignore_patterns):
                continue

            source_file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(source_file_path, local_directory_path)
            blob_name = os.path.join(blob_prefix, relative_path)

            # Create a blob
            blob = bucket.blob(blob_name)

            # Upload the file
            blob.upload_from_filename(source_file_path)
