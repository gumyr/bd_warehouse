from importlib import resources

import pytest
from build123d import IN
from build123d.objects_curve import Line

import bd_warehouse
from bd_warehouse.pipe import Pipe, PipeSection, _read_pipe_data


def test_pipe_data_lives_with_the_other_data_files():
    assert (resources.files(bd_warehouse) / "data" / "pipe.csv").is_file()


def test_read_pipe_data():
    pipe_data = _read_pipe_data()
    assert pipe_data["1/8steel40"] == (0.405, 0.068)
    assert pipe_data["1/8stainless10S"] == (0.405, 0.049)
    assert pipe_data["18steel160"] == (18.0, 1.781)


def test_pipe_section_dimensions():
    section = PipeSection("1/8", "stainless", "10S")
    assert section.od == pytest.approx(0.405 * IN)
    assert section.thickness == pytest.approx(0.049 * IN)
    size = section.bounding_box().size
    assert size.X == pytest.approx(0.405 * IN)
    assert size.Y == pytest.approx(0.405 * IN)


def test_pipe_along_path():
    pipe = Pipe("1/8", "stainless", "10S", path=Line((0, 0, 0), (0, 0, 10)))
    assert pipe.is_valid
    assert pipe.bounding_box().size.Z == pytest.approx(10)
