import os
import shutil
from pathlib import Path
from src.utils.print_utils import print_warning


def clear_repo(path: Path) -> None:
    """
    Clear a repository

    :param path: the path of the repository
    :return: None
    """
    try:
        # It is necessary to elevate permissions otherwise deleting fails
        for file in path.glob('.git/objects/pack/*.idx'):
            os.chmod(file, 0o777)
        for file in path.glob('.git/objects/pack/*.pack'):
            os.chmod(file, 0o777)

        shutil.rmtree(path)

    except Exception as e:
        print_warning(f'-failed to delete {path}. Reason: {e}')
