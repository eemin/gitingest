""" Tests for the query_parser module. """

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from gitingest.ignore_patterns import DEFAULT_IGNORE_PATTERNS
from gitingest.query_parser import _parse_patterns, _parse_repo_source, parse_query


async def test_parse_url_valid_https() -> None:
    """
    Test `_parse_repo_source` with valid HTTPS URLs from supported platforms (GitHub, GitLab, Bitbucket, Gitea).
    Verifies that user and repository names are correctly extracted.
    """
    test_cases = [
        "https://github.com/user/repo",
        "https://gitlab.com/user/repo",
        "https://bitbucket.org/user/repo",
        "https://gitea.com/user/repo",
        "https://codeberg.org/user/repo",
        "https://gitingest.com/user/repo",
    ]
    for url in test_cases:
        parsed_query = await _parse_repo_source(url)
        assert parsed_query.user_name == "user"
        assert parsed_query.repo_name == "repo"
        assert parsed_query.url == url


async def test_parse_url_valid_http() -> None:
    """
    Test `_parse_repo_source` with valid HTTP URLs from supported platforms.
    Verifies that user and repository names, as well as the slug, are correctly extracted.
    """
    test_cases = [
        "http://github.com/user/repo",
        "http://gitlab.com/user/repo",
        "http://bitbucket.org/user/repo",
        "http://gitea.com/user/repo",
        "http://codeberg.org/user/repo",
        "http://gitingest.com/user/repo",
    ]
    for url in test_cases:
        parsed_query = await _parse_repo_source(url)
        assert parsed_query.user_name == "user"
        assert parsed_query.repo_name == "repo"
        assert parsed_query.slug == "user-repo"


async def test_parse_url_invalid() -> None:
    """
    Test `_parse_repo_source` with an invalid URL that does not include a repository structure.
    Verifies that a ValueError is raised with an appropriate error message.
    """
    url = "https://github.com"
    with pytest.raises(ValueError, match="Invalid repository URL"):
        await _parse_repo_source(url)


async def test_parse_query_basic() -> None:
    """
    Test `parse_query` with basic inputs including valid repository URLs.
    Verifies that user and repository names, URL, and ignore patterns are correctly parsed.
    """
    test_cases = ["https://github.com/user/repo", "https://gitlab.com/user/repo"]
    for url in test_cases:
        parsed_query = await parse_query(url, max_file_size=50, from_web=True, ignore_patterns="*.txt")
        assert parsed_query.user_name == "user"
        assert parsed_query.repo_name == "repo"
        assert parsed_query.url == url
        assert parsed_query.ignore_patterns
        assert "*.txt" in parsed_query.ignore_patterns


async def test_parse_query_mixed_case() -> None:
    """
    Test `parse_query` with mixed case URLs.
    """
    url = "Https://GitHub.COM/UsEr/rEpO"
    parsed_query = await parse_query(url, max_file_size=50, from_web=True)
    assert parsed_query.user_name == "user"
    assert parsed_query.repo_name == "repo"


async def test_parse_query_include_pattern() -> None:
    """
    Test `parse_query` with an include pattern.
    Verifies that the include pattern is set correctly and default ignore patterns are applied.
    """
    url = "https://github.com/user/repo"
    parsed_query = await parse_query(url, max_file_size=50, from_web=True, include_patterns="*.py")
    assert parsed_query.include_patterns == {"*.py"}
    assert parsed_query.ignore_patterns == DEFAULT_IGNORE_PATTERNS


async def test_parse_query_invalid_pattern() -> None:
    """
    Test `parse_query` with an invalid pattern containing special characters.
    Verifies that a ValueError is raised with an appropriate error message.
    """
    url = "https://github.com/user/repo"
    with pytest.raises(ValueError, match="Pattern.*contains invalid characters"):
        await parse_query(url, max_file_size=50, from_web=True, include_patterns="*.py;rm -rf")


async def test_parse_url_with_subpaths() -> None:
    """
    Test `_parse_repo_source` with a URL containing a branch and subpath.
    Verifies that user name, repository name, branch, and subpath are correctly extracted.
    """
    url = "https://github.com/user/repo/tree/main/subdir/file"
    with patch("gitingest.repository_clone._run_git_command", new_callable=AsyncMock) as mock_run_git_command:
        mock_run_git_command.return_value = (b"refs/heads/main\nrefs/heads/dev\nrefs/heads/feature-branch\n", b"")
        with patch(
            "gitingest.repository_clone.fetch_remote_branch_list", new_callable=AsyncMock
        ) as mock_fetch_branches:
            mock_fetch_branches.return_value = ["main", "dev", "feature-branch"]
            parsed_query = await _parse_repo_source(url)
            assert parsed_query.user_name == "user"
            assert parsed_query.repo_name == "repo"
            assert parsed_query.branch == "main"
            assert parsed_query.subpath == "/subdir/file"


async def test_parse_url_invalid_repo_structure() -> None:
    """
    Test `_parse_repo_source` with an invalid repository structure in the URL.
    Verifies that a ValueError is raised with an appropriate error message.
    """
    url = "https://github.com/user"
    with pytest.raises(ValueError, match="Invalid repository URL"):
        await _parse_repo_source(url)


def test_parse_patterns_valid() -> None:
    """
    Test `_parse_patterns` with valid patterns separated by commas.
    Verifies that the patterns are correctly parsed into a list.
    """
    patterns = "*.py, *.md, docs/*"
    parsed_patterns = _parse_patterns(patterns)
    assert parsed_patterns == {"*.py", "*.md", "docs/*"}


def test_parse_patterns_invalid_characters() -> None:
    """
    Test `_parse_patterns` with invalid patterns containing special characters.
    Verifies that a ValueError is raised with an appropriate error message.
    """
    patterns = "*.py;rm -rf"
    with pytest.raises(ValueError, match="Pattern.*contains invalid characters"):
        _parse_patterns(patterns)


async def test_parse_query_with_large_file_size() -> None:
    """
    Test `parse_query` with a very large file size limit.
    Verifies that the file size limit and default ignore patterns are set correctly.
    """
    url = "https://github.com/user/repo"
    parsed_query = await parse_query(url, max_file_size=10**9, from_web=True)
    assert parsed_query.max_file_size == 10**9
    assert parsed_query.ignore_patterns == DEFAULT_IGNORE_PATTERNS


async def test_parse_query_empty_patterns() -> None:
    """
    Test `parse_query` with empty include and ignore patterns.
    Verifies that the include patterns are set to None and default ignore patterns are applied.
    """
    url = "https://github.com/user/repo"
    parsed_query = await parse_query(url, max_file_size=50, from_web=True, include_patterns="", ignore_patterns="")
    assert parsed_query.include_patterns is None
    assert parsed_query.ignore_patterns == DEFAULT_IGNORE_PATTERNS


async def test_parse_query_include_and_ignore_overlap() -> None:
    """
    Test `parse_query` with overlapping include and ignore patterns.
    Verifies that overlapping patterns are removed from the ignore patterns.
    """
    url = "https://github.com/user/repo"
    parsed_query = await parse_query(
        url,
        max_file_size=50,
        from_web=True,
        include_patterns="*.py",
        ignore_patterns={"*.py", "*.txt"},
    )
    assert parsed_query.include_patterns == {"*.py"}
    assert parsed_query.ignore_patterns is not None
    assert "*.py" not in parsed_query.ignore_patterns
    assert "*.txt" in parsed_query.ignore_patterns


async def test_parse_query_local_path() -> None:
    """
    Test `parse_query` with a local file path.
    Verifies that the local path is set, a unique ID is generated, and the slug is correctly created.
    """
    path = "/home/user/project"
    parsed_query = await parse_query(path, max_file_size=100, from_web=False)
    tail = Path("home/user/project")
    assert parsed_query.local_path.parts[-len(tail.parts) :] == tail.parts
    assert parsed_query.id is not None
    assert parsed_query.slug == "user/project"


async def test_parse_query_relative_path() -> None:
    """
    Test `parse_query` with a relative file path.
    Verifies that the local path and slug are correctly resolved.
    """
    path = "./project"
    parsed_query = await parse_query(path, max_file_size=100, from_web=False)
    tail = Path("project")
    assert parsed_query.local_path.parts[-len(tail.parts) :] == tail.parts
    assert parsed_query.slug.endswith("project")


async def test_parse_query_empty_source() -> None:
    """
    Test `parse_query` with an empty source input.
    Verifies that a ValueError is raised with an appropriate error message.
    """
    with pytest.raises(ValueError, match="Invalid repository URL"):
        await parse_query("", max_file_size=100, from_web=True)


async def test_parse_url_branch_and_commit_distinction() -> None:
    """
    Test `_parse_repo_source` with URLs containing either a branch name or a commit hash.
    Verifies that the branch and commit are correctly distinguished.
    """
    url_branch = "https://github.com/user/repo/tree/main"
    url_commit = "https://github.com/user/repo/tree/abcd1234abcd1234abcd1234abcd1234abcd1234"

    with patch("gitingest.repository_clone._run_git_command", new_callable=AsyncMock) as mock_run_git_command:
        mock_run_git_command.return_value = (b"refs/heads/main\nrefs/heads/dev\nrefs/heads/feature-branch\n", b"")
        with patch(
            "gitingest.repository_clone.fetch_remote_branch_list", new_callable=AsyncMock
        ) as mock_fetch_branches:
            mock_fetch_branches.return_value = ["main", "dev", "feature-branch"]

            parsed_query_with_branch = await _parse_repo_source(url_branch)
            parsed_query_with_commit = await _parse_repo_source(url_commit)

    assert parsed_query_with_branch.branch == "main"
    assert parsed_query_with_branch.commit is None

    assert parsed_query_with_commit.branch is None
    assert parsed_query_with_commit.commit == "abcd1234abcd1234abcd1234abcd1234abcd1234"


async def test_parse_query_uuid_uniqueness() -> None:
    """
    Test `parse_query` to ensure that each call generates a unique UUID for the query.
    """
    path = "/home/user/project"
    parsed_query_1 = await parse_query(path, max_file_size=100, from_web=False)
    parsed_query_2 = await parse_query(path, max_file_size=100, from_web=False)
    assert parsed_query_1.id != parsed_query_2.id


async def test_parse_url_with_query_and_fragment() -> None:
    """
    Test `_parse_repo_source` with a URL containing query parameters and a fragment.
    Verifies that the URL is cleaned and other fields are correctly extracted.
    """
    url = "https://github.com/user/repo?arg=value#fragment"
    parsed_query = await _parse_repo_source(url)
    assert parsed_query.user_name == "user"
    assert parsed_query.repo_name == "repo"
    assert parsed_query.url == "https://github.com/user/repo"  # URL should be cleaned


async def test_parse_url_unsupported_host() -> None:
    url = "https://only-domain.com"
    with pytest.raises(ValueError, match="Unknown domain 'only-domain.com' in URL"):
        await _parse_repo_source(url)


async def test_parse_query_with_branch() -> None:
    url = "https://github.com/pandas-dev/pandas/blob/2.2.x/.github/ISSUE_TEMPLATE/documentation_improvement.yaml"
    parsed_query = await parse_query(url, max_file_size=10**9, from_web=True)
    assert parsed_query.user_name == "pandas-dev"
    assert parsed_query.repo_name == "pandas"
    assert parsed_query.url == "https://github.com/pandas-dev/pandas"
    assert parsed_query.slug == "pandas-dev-pandas"
    assert parsed_query.id is not None
    assert parsed_query.subpath == "/.github/ISSUE_TEMPLATE/documentation_improvement.yaml"
    assert parsed_query.branch == "2.2.x"
    assert parsed_query.commit is None
    assert parsed_query.type == "blob"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url, expected_branch, expected_subpath",
    [
        ("https://github.com/user/repo/tree/main/src", "main", "/src"),
        ("https://github.com/user/repo/tree/fix1", "fix1", "/"),
        ("https://github.com/user/repo/tree/nonexistent-branch/src", "nonexistent-branch", "/src"),
    ],
)
async def test_parse_repo_source_with_failed_git_command(url, expected_branch, expected_subpath):
    """
    Test `_parse_repo_source` when git command fails.
    Verifies that the function returns the first path component as the branch.
    """
    with patch("gitingest.repository_clone.fetch_remote_branch_list", new_callable=AsyncMock) as mock_fetch_branches:
        mock_fetch_branches.side_effect = Exception("Failed to fetch branch list")

        parsed_query = await _parse_repo_source(url)

        assert parsed_query.branch == expected_branch
        assert parsed_query.subpath == expected_subpath


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url, expected_branch, expected_subpath",
    [
        ("https://github.com/user/repo/tree/feature/fix1/src", "feature/fix1", "/src"),
        ("https://github.com/user/repo/tree/main/src", "main", "/src"),
        ("https://github.com/user/repo", None, "/"),  # No
        ("https://github.com/user/repo/tree/nonexistent-branch/src", None, "/"),  # Non-existent branch
        ("https://github.com/user/repo/tree/fix", "fix", "/"),
        ("https://github.com/user/repo/blob/fix/page.html", "fix", "/page.html"),
    ],
)
async def test_parse_repo_source_with_various_url_patterns(url, expected_branch, expected_subpath):
    with (
        patch("gitingest.repository_clone._run_git_command", new_callable=AsyncMock) as mock_run_git_command,
        patch("gitingest.repository_clone.fetch_remote_branch_list", new_callable=AsyncMock) as mock_fetch_branches,
    ):

        mock_run_git_command.return_value = (
            b"refs/heads/feature/fix1\nrefs/heads/main\nrefs/heads/feature-branch\nrefs/heads/fix\n",
            b"",
        )
        mock_fetch_branches.return_value = ["feature/fix1", "main", "feature-branch"]

        parsed_query = await _parse_repo_source(url)
        assert parsed_query.branch == expected_branch
        assert parsed_query.subpath == expected_subpath
