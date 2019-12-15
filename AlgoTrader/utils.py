import subprocess


def get_git_revision_hash(short=False) -> str:
    """
    Get the sha1 hash of the current revision for the git repo.
    :param short: Whether or not to generate the short hash.
    :return: the sha1 hash of the current revision.
    """
    if short:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'])
    else:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'])
