"""Category H (AIG): unit tests for ImgDecorator image-decoration helpers.

These exercise pure PIL-based drawing/validation logic that backs the
overlay parameters accepted by `POST /aig/minf/` (price, promo, logo,
slogan, frame details).
"""
from PIL import Image

from imgproc.img_frame import ImgDecorator


def test_is_color_valid_accepts_known_color_names():
    assert ImgDecorator.is_color_valid("white") is True
    assert ImgDecorator.is_color_valid("Black") is True  # case-insensitive


def test_is_color_valid_rejects_unknown_or_invalid_input():
    assert ImgDecorator.is_color_valid("not-a-real-color") is False
    assert ImgDecorator.is_color_valid(None) is False
    assert ImgDecorator.is_color_valid(123) is False


def test_get_color_list_returns_non_empty_list_of_strings():
    colors = ImgDecorator.get_color_list()
    assert isinstance(colors, list)
    assert len(colors) > 0
    assert "white" in colors


def test_draw_frame_double_border_returns_image_of_same_size():
    img = Image.new("RGB", (200, 100), color="blue")
    result = ImgDecorator.draw_frame_double_border(img, percentageFromBorder=2)
    assert result.size == (200, 100)


def test_draw_frame_double_border_rejects_non_image_input():
    try:
        ImgDecorator.draw_frame_double_border("not-an-image")
        assert False, "expected TypeError"
    except TypeError:
        pass


def test_draw_frame_double_border_rejects_out_of_range_percentage():
    img = Image.new("RGB", (100, 100))
    for bad_value in (-1, 101):
        try:
            ImgDecorator.draw_frame_double_border(img, percentageFromBorder=bad_value)
            assert False, "expected ValueError"
        except ValueError:
            pass


def test_draw_frame_double_border_converts_non_rgb_image():
    img = Image.new("RGBA", (50, 50))
    result = ImgDecorator.draw_frame_double_border(img, percentageFromBorder=2)
    assert result.mode == "RGB"


def test_count_digits_counts_only_numeric_characters():
    assert ImgDecorator.count_digits("$12.50/lb") == 4
    assert ImgDecorator.count_digits("") == 0
    assert ImgDecorator.count_digits(None) == 0
    assert ImgDecorator.count_digits(1250) == 0  # not a string


def test_count_points_commas_counts_both():
    assert ImgDecorator.count_points_commas("1,234.56") == 2
    assert ImgDecorator.count_points_commas("no separators") == 0
    assert ImgDecorator.count_points_commas(None) == 0
