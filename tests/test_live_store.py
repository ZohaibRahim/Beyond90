import pytest

from beyond90.live import PrivateDataAccessError, load_public_match, read_public_file
from beyond90.schemas import validate_match
from beyond90.simulator import simulate_match, write_outputs


@pytest.fixture(scope="module")
def match_dir(tmp_path_factory):
    result = simulate_match(5)
    paths = write_outputs(result, tmp_path_factory.mktemp("data"))
    return paths["events"].parent.parent, result


def test_loads_public_match(match_dir):
    path, result = match_dir
    setup, events = load_public_match(path)
    assert validate_match(setup, events).score == result.ground_truth.final_score


@pytest.mark.parametrize("name", ["../private/ground_truth.json", "ground_truth.json", "../../x.json"])
def test_refuses_anything_but_public_files(match_dir, name):
    with pytest.raises(PrivateDataAccessError):
        read_public_file(match_dir[0], name)


def test_refuses_private_directory(match_dir):
    with pytest.raises(PrivateDataAccessError):
        load_public_match(match_dir[0] / "private")
